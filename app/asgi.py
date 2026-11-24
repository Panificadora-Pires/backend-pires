"""ASGI da Pires: HTTP preservado, WebSocket opt-in com ticket e origem validada."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

# Inicializa Django antes de importar consumers/ORM.
django_application = get_asgi_application()

from django.conf import settings  # noqa: E402

if settings.REALTIME_ENABLED:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import OriginValidator

    from realtime.auth import TicketAuthMiddleware
    from realtime.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        'http': django_application,
        'websocket': OriginValidator(
            TicketAuthMiddleware(URLRouter(websocket_urlpatterns)),
            settings.REALTIME_ALLOWED_ORIGINS,
        ),
    })
else:
    # Na configuração atual de produção, ASGI segue servindo somente HTTP.
    application = django_application
