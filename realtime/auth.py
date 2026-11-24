"""Autentica o WS via subprotocol: nunca transporta JWT de longa duração."""
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

from .tickets import TicketUnavailable, consumir_ticket

_PROTOCOL = 'pires.v1'
_TICKET_PREFIX = 'pires.ticket.'


@database_sync_to_async
def _conta_ativa(pk, papel):
    user = get_user_model().objects.filter(pk=pk, is_active=True).first()
    if not user or (papel == 'admin' and not user.is_staff):
        return None
    return user


class TicketAuthMiddleware:
    """Consome ticket Redis uma só vez antes de acessar qualquer consumer."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        protocolos = scope.get('subprotocols') or []
        candidatos = [
            item[len(_TICKET_PREFIX):]
            for item in protocolos
            if item.startswith(_TICKET_PREFIX)
        ]
        if _PROTOCOL not in protocolos or len(candidatos) != 1:
            await send({'type': 'websocket.close', 'code': 4401})
            return
        try:
            resultado = await sync_to_async(
                consumir_ticket, thread_sensitive=False
            )(candidatos[0])
            user = await _conta_ativa(*resultado) if resultado else None
        except (TicketUnavailable, ValueError, TypeError):
            user = None
        if user is None:
            await send({'type': 'websocket.close', 'code': 4401})
            return
        escopo = {**scope, 'user': user, 'realtime_papel': resultado[1]}
        return await self.app(escopo, receive, send)
