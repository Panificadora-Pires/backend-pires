# Generated for the authentication verification flow.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def mark_existing_users_as_verified(apps, schema_editor):
    """Preserva o acesso das contas existentes antes da verificação por e-mail."""

    User = apps.get_model('core', 'User')
    User.objects.update(email_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        (
            'core',
            '0007_user_google_sub_alter_user_email_and_more',
        ),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='phone',
            field=models.CharField(
                blank=True,
                help_text=(
                    'Telefone normalizado no formato internacional, '
                    'por exemplo +5547999999999.'
                ),
                max_length=20,
                null=True,
                unique=True,
                verbose_name='Telefone',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Indica se o usuário comprovou o controle '
                    'do endereço de e-mail.'
                ),
                verbose_name='E-mail verificado',
            ),
        ),
        migrations.CreateModel(
            name='VerificationCode',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'public_id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        verbose_name='Identificador público',
                    ),
                ),
                (
                    'purpose',
                    models.CharField(
                        choices=[
                            (
                                'account_activation',
                                'Ativação de conta',
                            ),
                            (
                                'password_reset',
                                'Redefinição de senha',
                            ),
                        ],
                        max_length=32,
                        verbose_name='Finalidade',
                    ),
                ),
                (
                    'code_hash',
                    models.CharField(
                        max_length=64,
                        verbose_name='Hash do código',
                    ),
                ),
                (
                    'expires_at',
                    models.DateTimeField(
                        verbose_name='Expira em',
                    ),
                ),
                (
                    'attempts',
                    models.PositiveSmallIntegerField(
                        default=0,
                        verbose_name='Tentativas',
                    ),
                ),
                (
                    'used_at',
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name='Utilizado em',
                    ),
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name='Criado em',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='verification_codes',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Usuário',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Código de verificação',
                'verbose_name_plural': 'Códigos de verificação',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='verificationcode',
            index=models.Index(
                fields=['user', 'purpose', '-created_at'],
                name='core_verif_user_purp_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='verificationcode',
            index=models.Index(
                fields=['expires_at'],
                name='core_verif_expires_idx',
            ),
        ),
        migrations.RunPython(
            mark_existing_users_as_verified,
            migrations.RunPython.noop,
        ),
    ]
