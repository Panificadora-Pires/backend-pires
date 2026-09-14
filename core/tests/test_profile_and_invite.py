import base64
import tempfile

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from core.models import AdminInvite, User
from core.tests.base import AuthAPITestCase


# PNG RGB 1x1 válido.
#
# O fixture anterior possuía checksum inválido no chunk IDAT e o Pillow,
# corretamente, rejeitava o upload antes de chegar à regra de negócio.
PNG_1X1 = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1Pe'
    'AAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC'
)


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

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data['phone'],
            '+5547999999999',
        )
        self.assertTrue(
            response.data['email_verified'],
        )
        self.assertIsNone(
            response.data['avatar'],
        )
        self.assertFalse(
            response.data['google_connected'],
        )
        self.assertTrue(
            response.data['has_usable_password'],
        )

    def test_me_patch_updates_name_and_phone_without_changing_email(self):
        user = User.objects.create_user(
            email='usuario@example.com',
            password=self.strong_password,
            name='Nome antigo',
            phone='+5547999999999',
            email_verified=True,
            is_active=True,
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            reverse('usuarios-me'),
            {
                'name': 'Nome Atualizado',
                'phone': '(47) 98888-7777',
                'email': 'tentativa@example.com',
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            response.data['name'],
            'Nome Atualizado',
        )
        self.assertEqual(
            response.data['phone'],
            '+5547988887777',
        )
        self.assertEqual(
            response.data['email'],
            'usuario@example.com',
        )

        user.refresh_from_db()

        self.assertEqual(
            user.email,
            'usuario@example.com',
        )
        self.assertEqual(
            user.name,
            'Nome Atualizado',
        )
        self.assertEqual(
            user.phone,
            '+5547988887777',
        )

    def test_me_patch_rejects_phone_already_used_by_another_user(self):
        User.objects.create_user(
            email='outro@example.com',
            password=self.strong_password,
            phone='+5547999999999',
            email_verified=True,
            is_active=True,
        )
        user = User.objects.create_user(
            email='usuario@example.com',
            password=self.strong_password,
            phone='+5547988887777',
            email_verified=True,
            is_active=True,
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            reverse('usuarios-me'),
            {'phone': '(47) 99999-9999'},
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn(
            'phone',
            response.data,
        )

    def test_me_patch_uploads_and_removes_avatar(self):
        user = User.objects.create_user(
            email='usuario@example.com',
            password=self.strong_password,
            name='Usuário',
            phone='+5547999999999',
            email_verified=True,
            is_active=True,
        )
        self.client.force_authenticate(user=user)

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(
                MEDIA_ROOT=media_root,
                STORAGES={
                    'default': {
                        'BACKEND': (
                            'django.core.files.storage.'
                            'FileSystemStorage'
                        ),
                    },
                    'staticfiles': {
                        'BACKEND': (
                            'django.contrib.staticfiles.storage.'
                            'StaticFilesStorage'
                        ),
                    },
                },
            ):
                avatar = SimpleUploadedFile(
                    'avatar.png',
                    PNG_1X1,
                    content_type='image/png',
                )

                upload = self.client.patch(
                    reverse('usuarios-me'),
                    {'avatar': avatar},
                    format='multipart',
                )

                self.assertEqual(
                    upload.status_code,
                    status.HTTP_200_OK,
                    upload.data,
                )
                self.assertTrue(
                    upload.data['avatar'],
                )

                user.refresh_from_db()

                self.assertTrue(bool(user.avatar))
                self.assertTrue(
                    user.avatar.name.startswith(
                        'usuarios/avatars/'
                    ),
                    user.avatar.name,
                )
                self.assertTrue(
                    user.avatar.storage.exists(
                        user.avatar.name,
                    )
                )

                remove = self.client.patch(
                    reverse('usuarios-me'),
                    {'remove_avatar': True},
                    format='json',
                )

                self.assertEqual(
                    remove.status_code,
                    status.HTTP_200_OK,
                    remove.data,
                )
                self.assertIsNone(
                    remove.data['avatar'],
                )

                user.refresh_from_db()
                self.assertFalse(
                    bool(user.avatar),
                )

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
        self.assertEqual(
            len(mail.outbox),
            1,
        )

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

        user = User.objects.get(
            email=invite.email,
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertTrue(user.email_verified)
