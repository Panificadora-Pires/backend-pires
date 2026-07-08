from django.apps import AppConfig


class NotificacoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notificacoes'

    def ready(self):
        # Conecta o receiver que escuta pedidos.signals.pedido_ficou_pronto.
        # Precisa ser importado aqui (e não no topo do módulo) para rodar só
        # depois que todos os apps já foram carregados pelo Django.
        from . import receivers  # noqa: F401, PLC0415
