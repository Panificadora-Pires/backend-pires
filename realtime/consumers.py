"""Consumer somente-leitura: cliente nunca altera pedidos por WebSocket."""
import asyncio
import json

from django.conf import settings

from channels.generic.websocket import AsyncWebsocketConsumer

_EVENTOS = frozenset({
    'pedido.criado',
    'pedido.atualizado',
    'chat.mensagem_nova',
    'chat.leitura_atualizada',
    'notificacao.alterada',
})
_CAMPOS = frozenset({'v', 'tipo', 'pedido_id', 'event_id', 'emitido_em'})


class EventsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        papel = self.scope.get('realtime_papel')
        if not user or not user.is_authenticated or papel not in ('admin', 'usuario'):
            await self.close(code=4403)
            return
        if papel == 'admin' and not user.is_staff:
            await self.close(code=4403)
            return
        self.grupo = 'pires-admin-eventos' if papel == 'admin' else f'pires-usuario-{user.pk}'
        try:
            await self.channel_layer.group_add(self.grupo, self.channel_name)
        except Exception:
            await self.close(code=1013)
            return
        await self.accept(subprotocol='pires.v1')
        self._expiracao_tarefa = asyncio.create_task(self._expirar_conexao())

    async def _expirar_conexao(self):
        try:
            await asyncio.sleep(settings.REALTIME_MAX_CONNECTION_SECONDS)
        except asyncio.CancelledError:
            return
        await self.close(code=4401)

    async def disconnect(self, close_code):
        if hasattr(self, '_expiracao_tarefa'):
            self._expiracao_tarefa.cancel()
        if hasattr(self, 'grupo'):
            try:
                await self.channel_layer.group_discard(self.grupo, self.channel_name)
            except Exception:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        await self.close(code=4403)

    async def realtime_event(self, event):
        dados = event.get('payload')
        if not isinstance(dados, dict) or dados.get('v') != 1 or dados.get('tipo') not in _EVENTOS:
            return
        await self.send(text_data=json.dumps({
            chave: valor for chave, valor in dados.items() if chave in _CAMPOS
        }))
