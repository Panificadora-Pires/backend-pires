"""Modelo de desafios de verificação por e-mail."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class VerificationCode(models.Model):
    """Desafio temporário usado para ativação e redefinição de senha."""

    class Purpose(models.TextChoices):
        ACCOUNT_ACTIVATION = (
            'account_activation',
            _('Ativação de conta'),
        )
        PASSWORD_RESET = (
            'password_reset',
            _('Redefinição de senha'),
        )

    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name=_('Identificador público'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_codes',
        verbose_name=_('Usuário'),
    )

    purpose = models.CharField(
        max_length=32,
        choices=Purpose.choices,
        verbose_name=_('Finalidade'),
    )

    code_hash = models.CharField(
        max_length=64,
        verbose_name=_('Hash do código'),
    )

    expires_at = models.DateTimeField(
        verbose_name=_('Expira em'),
    )

    attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('Tentativas'),
    )

    used_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Utilizado em'),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em'),
    )

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    def __str__(self):
        return f'{self.user} — {self.get_purpose_display()}'

    class Meta:
        verbose_name = 'Código de verificação'
        verbose_name_plural = 'Códigos de verificação'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['user', 'purpose', '-created_at'],
                name='core_verif_user_purp_idx',
            ),
            models.Index(
                fields=['expires_at'],
                name='core_verif_expires_idx',
            ),
        ]
