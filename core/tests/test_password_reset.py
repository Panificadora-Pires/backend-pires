from django.core import mail
from django.urls import reverse
from rest_framework import status

from core.models import User, VerificationCode
from core.tests.base import AuthAPITestCase


class PasswordResetTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email='usuario@example.com',
            password='SenhaAntiga!2026',
            name='Usuário Teste',
            phone='+5547999999999',
            email_verified=True,
            is_active=True,
        )

    def request_reset(self, email='usuario@example.com'):
        return self.client.post(
            reverse('password_reset_request'),
            {'email': email},
            format='json',
        )

    def test_request_reset_sends_code_for_eligible_user(self):
        response = self.request_reset()

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 1)

        challenge = VerificationCode.objects.get(
            public_id=response.data['verification_id'],
            user=self.user,
            purpose=VerificationCode.Purpose.PASSWORD_RESET,
        )
        self.assertIsNone(challenge.used_at)

    def test_unknown_email_returns_same_status_without_creating_challenge(self):
        response = self.request_reset('naoexiste@example.com')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(
            VerificationCode.objects.filter(
                purpose=VerificationCode.Purpose.PASSWORD_RESET,
            ).count(),
            0,
        )
        self.assertIn('verification_id', response.data)

    def test_correct_code_changes_password(self):
        request_response = self.request_reset()
        code = self.latest_email_code()

        reset = self.client.post(
            reverse('password_reset_confirm'),
            {
                'request_id': request_response.data['verification_id'],
                'code': code,
                'new_password': 'SenhaNova!2026',
            },
            format='json',
        )

        self.assertEqual(reset.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('SenhaNova!2026'))
        self.assertFalse(self.user.check_password('SenhaAntiga!2026'))

        challenge = VerificationCode.objects.get(
            public_id=request_response.data['verification_id'],
        )
        self.assertIsNotNone(challenge.used_at)

    def test_wrong_reset_code_increments_attempts(self):
        request_response = self.request_reset()
        code = self.latest_email_code()
        wrong_code = '000000' if code != '000000' else '999999'

        response = self.client.post(
            reverse('password_reset_confirm'),
            {
                'request_id': request_response.data['verification_id'],
                'code': wrong_code,
                'new_password': 'SenhaNova!2026',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        challenge = VerificationCode.objects.get(
            public_id=request_response.data['verification_id'],
        )
        self.assertEqual(challenge.attempts, 1)

    def test_weak_password_does_not_consume_valid_code(self):
        request_response = self.request_reset()
        code = self.latest_email_code()

        response = self.client.post(
            reverse('password_reset_confirm'),
            {
                'request_id': request_response.data['verification_id'],
                'code': code,
                'new_password': '12345678',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)

        challenge = VerificationCode.objects.get(
            public_id=request_response.data['verification_id'],
        )
        self.assertIsNone(challenge.used_at)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('SenhaAntiga!2026'))

    def test_reset_code_cannot_be_reused(self):
        request_response = self.request_reset()
        code = self.latest_email_code()
        request_id = request_response.data['verification_id']

        first = self.client.post(
            reverse('password_reset_confirm'),
            {
                'request_id': request_id,
                'code': code,
                'new_password': 'SenhaNova!2026',
            },
            format='json',
        )
        second = self.client.post(
            reverse('password_reset_confirm'),
            {
                'request_id': request_id,
                'code': code,
                'new_password': 'OutraSenha!2026',
            },
            format='json',
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_old_access_token_is_rejected_after_password_change(self):
        login = self.client.post(
            reverse('token_obtain_pair'),
            {
                'email': self.user.email,
                'password': 'SenhaAntiga!2026',
            },
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        old_access = login.data['access']

        request_response = self.request_reset()
        code = self.latest_email_code()

        reset = self.client.post(
            reverse('password_reset_confirm'),
            {
                'request_id': request_response.data['verification_id'],
                'code': code,
                'new_password': 'SenhaNova!2026',
            },
            format='json',
        )
        self.assertEqual(reset.status_code, status.HTTP_200_OK)

        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {old_access}',
        )
        me = self.client.get(
            reverse('usuarios-me'),
        )
        self.assertEqual(me.status_code, status.HTTP_401_UNAUTHORIZED)
    def test_email_failure_invalidates_reset_challenge_without_leaking_error(self):
        from unittest.mock import patch

        with patch(
            'core.views.verification.send_password_reset_email',
            side_effect=OSError('smtp offline'),
        ):
            response = self.request_reset()

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        challenge = VerificationCode.objects.get(
            public_id=response.data['verification_id'],
        )
        self.assertIsNotNone(challenge.used_at)

    def test_weak_password_can_be_corrected_using_same_valid_code(self):
        request_response = self.request_reset()
        code = self.latest_email_code()
        request_id = request_response.data['verification_id']

        weak = self.client.post(
            reverse('password_reset_confirm'),
            {
                'request_id': request_id,
                'code': code,
                'new_password': '12345678',
            },
            format='json',
        )
        self.assertEqual(weak.status_code, status.HTTP_400_BAD_REQUEST)

        strong = self.client.post(
            reverse('password_reset_confirm'),
            {
                'request_id': request_id,
                'code': code,
                'new_password': 'SenhaCorrigida!2026',
            },
            format='json',
        )
        self.assertEqual(strong.status_code, status.HTTP_200_OK)


    def test_unknown_email_placeholder_is_stable_during_cooldown(self):
        first = self.request_reset('naoexiste@example.com')
        second = self.request_reset('naoexiste@example.com')

        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(second.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(
            first.data['verification_id'],
            second.data['verification_id'],
        )
        self.assertEqual(len(mail.outbox), 0)
