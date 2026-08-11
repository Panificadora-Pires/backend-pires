from django.core import mail
from django.urls import reverse
from rest_framework import status

from core.models import AdminInvite, User
from core.tests.base import AuthAPITestCase


class ProfileAndInviteTests(AuthAPITestCase):
    def test_me_exposes_contact_and_verification_status(self):
        user = User.objects.create_user(
            email='usuario@example.com',
            password=self.strong_password,
            name='Usuário',
            phone='+5547999999999',
            email_verified=True,
            is_active=True,
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(
            reverse('usuarios-me'),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone'], '+5547999999999')
        self.assertTrue(response.data['email_verified'])

    def test_invited_admin_is_considered_email_verified(self):
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='SenhaAdmin!2026',
        )
        self.client.force_authenticate(user=admin)

        create_invite = self.client.post(
            reverse('admin_invite_create'),
            {'email': 'novo-admin@example.com'},
            format='json',
        )
        self.assertEqual(
            create_invite.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(len(mail.outbox), 1)

        invite = AdminInvite.objects.get(
            email='novo-admin@example.com',
        )

        self.client.force_authenticate(user=None)
        registration = self.client.post(
            reverse('admin_invite_register'),
            {
                'token': str(invite.token),
                'name': 'Novo Admin',
                'email': invite.email,
                'password': 'SenhaAdminNova!2026',
            },
            format='json',
        )

        self.assertEqual(
            registration.status_code,
            status.HTTP_201_CREATED,
        )

        user = User.objects.get(email=invite.email)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertTrue(user.email_verified)
