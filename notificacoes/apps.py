from django.apps import AppConfig

from . import receivers  # noqa: F401


class NotificacoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notificacoes'
