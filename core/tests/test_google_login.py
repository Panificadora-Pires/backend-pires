from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from core.models import User
from core.tests.base import AuthAPITestCase


class GoogleLoginTests(AuthAPITestCase):
    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_google_picture_is_available_in_profile(self, verify):
        payload = self.google_payload()
        payload['picture'] = 'https://lh3.googleusercontent.com/a/foto-teste'
        verify.return_value = payload

        response = self.post_google()

        assert response.status_code == status.HTTP_200_OK
        user = User.objects.get(email='google@example.com')
        self.client.force_authenticate(user=user)
        profile = self.client.get(reverse('usuarios-me'))
        assert profile.data['avatar'] == payload['picture']

    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_existing_google_user_receives_picture_on_next_login(self, verify):
        user = User.objects.create_user(
            email='google@example.com', password=None, google_sub='google-sub-123',
            email_verified=True, is_active=True,
        )
        payload = self.google_payload()
        payload['picture'] = 'https://lh3.googleusercontent.com/a/atualizada'
        verify.return_value = payload

        assert self.post_google().status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.google_avatar_url == payload['picture']

    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_google_picture_does_not_replace_uploaded_avatar(self, verify):
        user = User.objects.create_user(
            email='google@example.com', password=None, google_sub='google-sub-123',
            email_verified=True, is_active=True, avatar='usuarios/avatars/manual.png',
        )
        payload = self.google_payload()
        payload['picture'] = 'https://lh3.googleusercontent.com/a/foto-google'
        verify.return_value = payload

        assert self.post_google().status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.avatar.name == 'usuarios/avatars/manual.png'
        self.client.force_authenticate(user=user)
        profile = self.client.get(reverse('usuarios-me'))
        assert profile.data['avatar'] != payload['picture']
        assert 'manual.png' in profile.data['avatar']

    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_missing_picture_preserves_previous_google_photo(self, verify):
        photo = 'https://lh3.googleusercontent.com/a/anterior'
        user = User.objects.create_user(
            email='google@example.com', password=None, google_sub='google-sub-123',
            email_verified=True, is_active=True, google_avatar_url=photo,
        )
        verify.return_value = self.google_payload()

        assert self.post_google().status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.google_avatar_url == photo

    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_unsafe_picture_is_ignored_without_blocking_login(self, verify):
        for picture in (
            'http://lh3.googleusercontent.com/a/foto',
            'https://example.com/foto',
            'https://googleusercontent.com.example.com/foto',
            'javascript:alert(1)',
            'https://[',
            'https://lh3.googleusercontent.com/' + 'a' * 2050,
        ):
            with self.subTest(picture=picture[:80]):
                payload = self.google_payload()
                payload['picture'] = picture
                verify.return_value = payload
                assert self.post_google().status_code == status.HTTP_200_OK
                user = User.objects.get(email='google@example.com')
                assert not user.google_avatar_url

    def test_profile_can_remove_google_photo_but_cannot_set_its_url(self):
        photo = 'https://lh3.googleusercontent.com/a/anterior'
        user = User.objects.create_user(
            email='google@example.com', password=None, google_sub='google-sub-123',
            email_verified=True, is_active=True, google_avatar_url=photo,
        )
        self.client.force_authenticate(user=user)
        injected = self.client.patch(
            reverse('usuarios-me'), {'google_avatar_url': 'https://example.com/foto'}, format='json',
        )
        assert injected.status_code == status.HTTP_200_OK
        assert injected.data['avatar'] == photo
        removed = self.client.patch(reverse('usuarios-me'), {'remove_avatar': True}, format='json')
        assert removed.status_code == status.HTTP_200_OK
        assert removed.data['avatar'] is None
        user.refresh_from_db()
        assert not user.google_avatar_url

    def google_payload(
        self,
        *,
        sub='google-sub-123',
        email='google@example.com',
        name='Google User',
    ):
        return {
            'iss': 'https://accounts.google.com',
            'sub': sub,
            'email': email,
            'email_verified': True,
            'name': name,
        }

    def post_google(self):
        return self.client.post(
            reverse('google_login'),
            {'credential': 'fake-google-id-token'},
            format='json',
        )

    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_google_creates_active_verified_user(self, verify):
        verify.return_value = self.google_payload()

        response = self.post_google()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        user = User.objects.get(email='google@example.com')
        self.assertEqual(user.google_sub, 'google-sub-123')
        self.assertTrue(user.email_verified)
        self.assertTrue(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertIsNone(user.phone)

    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_google_activates_pending_local_account(self, verify):
        user = User.objects.create_user(
            email='google@example.com',
            password='SenhaLocal!2026',
            phone='+5547999999999',
            email_verified=False,
            is_active=False,
        )
        verify.return_value = self.google_payload()

        response = self.post_google()

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertEqual(user.google_sub, 'google-sub-123')
        self.assertTrue(user.email_verified)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password('SenhaLocal!2026'))

    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_google_does_not_reactivate_suspended_verified_account(self, verify):
        user = User.objects.create_user(
            email='google@example.com',
            password='SenhaLocal!2026',
            email_verified=True,
            is_active=False,
        )
        verify.return_value = self.google_payload()

        response = self.post_google()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertIsNone(user.google_sub)

    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_existing_google_identity_is_not_duplicated(self, verify):
        user = User.objects.create_user(
            email='google@example.com',
            password=None,
            google_sub='google-sub-123',
            email_verified=True,
            is_active=True,
        )
        verify.return_value = self.google_payload()

        response = self.post_google()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.count(), 1)
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_google_rejects_unverified_google_email(self, verify):
        payload = self.google_payload()
        payload['email_verified'] = False
        verify.return_value = payload

        response = self.post_google()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 0)
    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_invalid_google_token_is_rejected(self, verify):
        verify.side_effect = ValueError('invalid audience')

        response = self.post_google()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 0)

    @patch('core.views.social.id_token.verify_oauth2_token')
    def test_google_rejects_conflicting_google_identity(self, verify):
        User.objects.create_user(
            email='google@example.com',
            password=None,
            google_sub='outro-google-sub',
            email_verified=True,
            is_active=True,
        )
        verify.return_value = self.google_payload(
            sub='google-sub-123',
        )

        response = self.post_google()

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(User.objects.count(), 1)

