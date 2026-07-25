import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class AdminInvite(models.Model):
    """Modelo para convites de criação de conta Admin."""
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_invites'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Configura expiração para 48h ao criar
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(hours=48)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Verifica se o convite ainda é válido."""
        return not self.used and self.expires_at > timezone.now()

    class Meta:
        verbose_name = 'Convite de Admin'
        verbose_name_plural = 'Convites de Admin'
