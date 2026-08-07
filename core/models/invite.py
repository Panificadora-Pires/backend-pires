import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class AdminInvite(models.Model):
    """Convite para criação de uma conta administrativa."""

    EXPIRATION_HOURS = 48

    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    email = models.EmailField(
        unique=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_invites',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    expires_at = models.DateTimeField()

    used = models.BooleanField(
        default=False,
    )

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()

        if not self.expires_at:
            self.expires_at = (
                timezone.now()
                + timedelta(hours=self.EXPIRATION_HOURS)
            )

        super().save(*args, **kwargs)

    def renew(self, created_by):
        """
        Gera um novo token para um convite já existente.

        O token anterior deixa de funcionar.
        """

        self.token = uuid.uuid4()
        self.created_by = created_by
        self.used = False
        self.expires_at = (
            timezone.now()
            + timedelta(hours=self.EXPIRATION_HOURS)
        )

        self.save(
            update_fields=[
                'token',
                'created_by',
                'used',
                'expires_at',
            ]
        )

    def is_valid(self):
        """Verifica se o convite ainda pode ser utilizado."""

        return (
            not self.used
            and self.expires_at > timezone.now()
        )

    def __str__(self):
        return self.email

    class Meta:
        verbose_name = 'Convite de Admin'
        verbose_name_plural = 'Convites de Admin'
