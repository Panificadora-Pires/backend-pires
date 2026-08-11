from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from core.models import User, VerificationCode
from core.tests.base import AuthAPITestCase


class RegistrationTests(AuthAPITestCase):
    def registration_payload(self, **overrides):
        payload = {
            'name': 'Arthur Teste',
            'email': 'Arthur.Teste@Example.COM',
            'phone': '(47) 99999-9999',
            'password': self.strong_password,
        }
        payload.update(overrides)
        return payload

    def register(self, **overrides):
        return self.client.post(
            reverse('user_registration'),
            self.registration_payload(**overrides),
            format='json',
        )

    def test_registration_creates_inactive_unverified_user_and_sends_code(self):
        response = self.register()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['email_sent'])
        self.assertEqual(len(mail.outbox), 1)

        user = User.objects.get(email='arthur.teste@example.com')
        self.assertFalse(user.is_active)
        self.assertFalse(user.email_verified)
        self.assertEqual(user.phone, '+5547999999999')
        self.assertTrue(user.check_password(self.strong_password))

        challenge = VerificationCode.objects.get(
            user=user,
            purpose=VerificationCode.Purpose.ACCOUNT_ACTIVATION,
        )
        self.assertEqual(
            str(challenge.public_id),
            response.data['verification_id'],
        )

        code = self.latest_email_code()
        self.assertNotEqual(challenge.code_hash, code)
        self.assertNotIn(code, challenge.code_hash)

    def test_registration_rejects_duplicate_email_case_insensitive(self):
        User.objects.create_user(
            email='arthur.teste@example.com',
            password=self.strong_password,
            phone='+5547999999999',
        )

        response = self.register(
            email='ARTHUR.TESTE@EXAMPLE.COM',
            phone='(47) 98888-8888',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_registration_rejects_duplicate_phone(self):
        User.objects.create_user(
            email='outro@example.com',
            password=self.strong_password,
            phone='+5547999999999',
        )

        response = self.register(
            email='novo@example.com',
            phone='+55 47 99999-9999',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_registration_rejects_invalid_phone(self):
        response = self.register(
            phone='12345',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_unverified_user_cannot_login(self):
        self.register()

        response = self.client.post(
            reverse('token_obtain_pair'),
            {
                'email': 'arthur.teste@example.com',
                'password': self.strong_password,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_correct_code_activates_account_and_enables_login(self):
        registration = self.register()
        code = self.latest_email_code()

        confirm = self.client.post(
            reverse('account_activation_confirm'),
            {
                'request_id': registration.data['verification_id'],
                'code': code,
            },
            format='json',
        )

        self.assertEqual(confirm.status_code, status.HTTP_200_OK)

        user = User.objects.get(email='arthur.teste@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.email_verified)

        login = self.client.post(
            reverse('token_obtain_pair'),
            {
                'email': user.email,
                'password': self.strong_password,
            },
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn('access', login.data)
        self.assertIn('refresh', login.data)

    def test_wrong_code_persists_attempt_counter(self):
        registration = self.register()

        response = self.client.post(
            reverse('account_activation_confirm'),
            {
                'request_id': registration.data['verification_id'],
                'code': '000000',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        challenge = VerificationCode.objects.get(
            public_id=registration.data['verification_id'],
        )
        self.assertEqual(challenge.attempts, 1)
        self.assertIsNone(challenge.used_at)

    def test_five_wrong_attempts_block_challenge(self):
        registration = self.register()
        code = self.latest_email_code()
        wrong_code = '000000' if code != '000000' else '999999'

        for _ in range(5):
            response = self.client.post(
                reverse('account_activation_confirm'),
                {
                    'request_id': registration.data['verification_id'],
                    'code': wrong_code,
                },
                format='json',
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
            )

        challenge = VerificationCode.objects.get(
            public_id=registration.data['verification_id'],
        )
        self.assertEqual(challenge.attempts, 5)
        self.assertIsNotNone(challenge.used_at)

        response = self.client.post(
            reverse('account_activation_confirm'),
            {
                'request_id': registration.data['verification_id'],
                'code': code,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_code_is_rejected_and_marked_used(self):
        registration = self.register()
        code = self.latest_email_code()

        VerificationCode.objects.filter(
            public_id=registration.data['verification_id'],
        ).update(
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.post(
            reverse('account_activation_confirm'),
            {
                'request_id': registration.data['verification_id'],
                'code': code,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        challenge = VerificationCode.objects.get(
            public_id=registration.data['verification_id'],
        )
        self.assertIsNotNone(challenge.used_at)

    def test_code_cannot_be_reused(self):
        registration = self.register()
        code = self.latest_email_code()
        payload = {
            'request_id': registration.data['verification_id'],
            'code': code,
        }

        first = self.client.post(
            reverse('account_activation_confirm'),
            payload,
            format='json',
        )
        second = self.client.post(
            reverse('account_activation_confirm'),
            payload,
            format='json',
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_within_cooldown_reuses_challenge_without_sending_again(self):
        registration = self.register()
        self.assertEqual(len(mail.outbox), 1)

        response = self.client.post(
            reverse('account_activation_resend'),
            {'email': 'arthur.teste@example.com'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            response.data['verification_id'],
            registration.data['verification_id'],
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_after_cooldown_invalidates_old_code(self):
        registration = self.register()
        old_id = registration.data['verification_id']

        VerificationCode.objects.filter(
            public_id=old_id,
        ).update(
            created_at=timezone.now() - timedelta(seconds=61),
        )

        response = self.client.post(
            reverse('account_activation_resend'),
            {'email': 'arthur.teste@example.com'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertNotEqual(response.data['verification_id'], old_id)
        self.assertEqual(len(mail.outbox), 2)

        old = VerificationCode.objects.get(public_id=old_id)
        self.assertIsNotNone(old.used_at)
    def test_email_failure_keeps_account_inactive_and_invalidates_challenge(self):
        from unittest.mock import patch

        with patch(
            'core.views.user.send_account_activation_email',
            side_effect=OSError('smtp offline'),
        ):
            response = self.register(
                email='falha@example.com',
                phone='(47) 97777-7777',
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['email_sent'])

        user = User.objects.get(email='falha@example.com')
        self.assertFalse(user.is_active)
        self.assertFalse(user.email_verified)

        challenge = VerificationCode.objects.get(user=user)
        self.assertIsNotNone(challenge.used_at)

    def test_resend_unknown_email_is_generic_and_sends_nothing(self):
        response = self.client.post(
            reverse('account_activation_resend'),
            {'email': 'desconhecido@example.com'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('verification_id', response.data)
        self.assertEqual(
            response.data['retry_after_seconds'],
            60,
        )
        self.assertEqual(len(mail.outbox), 0)


    def test_unknown_resend_placeholder_is_stable_during_cooldown(self):
        first = self.client.post(
            reverse('account_activation_resend'),
            {'email': 'desconhecido@example.com'},
            format='json',
        )
        second = self.client.post(
            reverse('account_activation_resend'),
            {'email': 'desconhecido@example.com'},
            format='json',
        )

        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(second.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            first.data['verification_id'],
            second.data['verification_id'],
        )
        self.assertEqual(len(mail.outbox), 0)
