from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def atualizar_foto_google(usuario, picture):
    """Guarda a URL do token já verificado, sem baixar mídia nem substituir uploads."""
    if not isinstance(picture, str):
        return
    foto = picture.strip()
    if not foto:
        return
    try:
        URLValidator(schemes=['https'])(foto)
        host = urlsplit(foto).hostname or ''
    except (ValidationError, ValueError):
        return
    if host != 'googleusercontent.com' and not host.endswith('.googleusercontent.com'):
        return
    if usuario.google_avatar_url != foto:
        usuario.google_avatar_url = foto
        usuario.save(update_fields=['google_avatar_url'])
