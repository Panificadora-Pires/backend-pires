"""
Validadores reutilizáveis (imagens de produto, etc).
"""

import os

from django.core.exceptions import ValidationError

IMAGEM_EXTENSOES_VALIDAS = ['.jpg', '.jpeg', '.png', '.webp']
IMAGEM_TAMANHO_MAXIMO_MB = 5


def validar_tipo_imagem(arquivo):
    """Aceita apenas extensões de imagem conhecidas."""
    extensao = os.path.splitext(arquivo.name)[1].lower()
    if extensao not in IMAGEM_EXTENSOES_VALIDAS:
        raise ValidationError(
            f'Tipo de arquivo não suportado ({extensao}). Use: {", ".join(IMAGEM_EXTENSOES_VALIDAS)}.'
        )


def validar_tamanho_imagem(arquivo):
    """Limita o tamanho do upload (evita estourar o plano gratuito do Cloudinary)."""
    limite_bytes = IMAGEM_TAMANHO_MAXIMO_MB * 1024 * 1024
    if arquivo.size > limite_bytes:
        raise ValidationError(f'A imagem deve ter no máximo {IMAGEM_TAMANHO_MAXIMO_MB}MB.')
