"""Validadores reutilizáveis do app core."""

from django.core.exceptions import ValidationError

MAX_AVATAR_SIZE_BYTES = 3 * 1024 * 1024


def validar_tamanho_avatar(arquivo):
    """Limita avatares a 3 MB para evitar uploads excessivos."""

    tamanho = getattr(arquivo, 'size', 0) or 0

    if tamanho > MAX_AVATAR_SIZE_BYTES:
        raise ValidationError(
            'A foto de perfil deve ter no máximo 3 MB.'
        )
