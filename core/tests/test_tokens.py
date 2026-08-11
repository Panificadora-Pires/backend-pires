from django.urls import reverse
from rest_framework import status

from core.models import User
from core.tests.base import AuthAPITestCase


class TokenSecurityTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email='token@example.com',
            password='SenhaToken!2026',
            email_verified=True,
            is_active=True,
        )

    def obtain_pair(self):
        return self.client.post(
            reverse('token_obtain_pair'),
            {
                'email': self.user.email,
                'password': 'SenhaToken!2026',
            },
            format='json',
        )

    def test_refresh_rotation_returns_new_refresh_and_blacklists_old_one(self):
        login = self.obtain_pair()
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        old_refresh = login.data['refresh']

        refreshed = self.client.post(
            reverse('token_refresh'),
            {'refresh': old_refresh},
            format='json',
        )

        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertIn('access', refreshed.data)
        self.assertIn('refresh', refreshed.data)
        self.assertNotEqual(refreshed.data['refresh'], old_refresh)

        reused = self.client.post(
            reverse('token_refresh'),
            {'refresh': old_refresh},
            format='json',
        )
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        login = self.obtain_pair()
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        refresh = login.data['refresh']

        logout = self.client.post(
            reverse('token_logout'),
            {'refresh': refresh},
            format='json',
        )
        self.assertEqual(logout.status_code, status.HTTP_204_NO_CONTENT)

        reused = self.client.post(
            reverse('token_refresh'),
            {'refresh': refresh},
            format='json',
        )
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_active_but_unverified_user_cannot_obtain_tokens(self):
        pending = User.objects.create_user(
            email='pendente@example.com',
            password='SenhaPendente!2026',
            email_verified=False,
            is_active=True,
        )

        response = self.client.post(
            reverse('token_obtain_pair'),
            {
                'email': pending.email,
                'password': 'SenhaPendente!2026',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('access', response.data)
        self.assertNotIn('refresh', response.data)
