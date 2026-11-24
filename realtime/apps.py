from django.apps import AppConfig


class RealtimeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'realtime'

    def ready(self):
        # Só registra listeners; a feature flag é verificada em cada emissão.
        from . import signals  # noqa: F401
