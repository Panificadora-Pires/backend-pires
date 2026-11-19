"""Testes do handshake ASGI após instalar Channels em ambiente de desenvolvimento."""
import asyncio
import importlib.util
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from django.test import override_settings


class HandshakeTestCase(TestCase):
    def setUp(self):
        if importlib.util.find_spec('channels') is None:
            self.skipTest('PR6A.1: executar quando PDM lock incluir Channels')

    @override_settings(REALTIME_ENABLED=True)
    def test_sem_ticket_fecha_ws_antes_da_aplicacao(self):
        from realtime.auth import TicketAuthMiddleware

        app = AsyncMock()
        middleware = TicketAuthMiddleware(app)
        saidas = []

        async def send(message):
            saidas.append(message)

        asyncio.run(middleware(
            {'type': 'websocket', 'subprotocols': ['pires.v1']},
            AsyncMock(),
            send,
        ))
        self.assertEqual(saidas, [{'type': 'websocket.close', 'code': 4401}])
        app.assert_not_awaited()

    @override_settings(REALTIME_ENABLED=True)
    def test_ticket_ausente_ou_reutilizado_fecha_ws(self):
        from realtime.auth import TicketAuthMiddleware

        app = AsyncMock()
        middleware = TicketAuthMiddleware(app)
        saidas = []

        async def send(message):
            saidas.append(message)

        with patch('realtime.auth.consumir_ticket', return_value=None):
            asyncio.run(middleware(
                {'type': 'websocket', 'subprotocols': ['pires.v1', 'pires.ticket.' + ('a' * 43)]},
                AsyncMock(),
                send,
            ))
        self.assertEqual(saidas, [{'type': 'websocket.close', 'code': 4401}])
        app.assert_not_awaited()

    @override_settings(REALTIME_ENABLED=True)
    def test_ticket_admin_sem_permissao_nao_aceita(self):
        from realtime.auth import TicketAuthMiddleware

        app = AsyncMock()
        middleware = TicketAuthMiddleware(app)
        saidas = []

        async def send(message):
            saidas.append(message)

        with (
            patch('realtime.auth.consumir_ticket', return_value=(2, 'admin')),
            patch('realtime.auth._conta_ativa', new_callable=AsyncMock, return_value=None),
        ):
            asyncio.run(middleware(
                {'type': 'websocket', 'subprotocols': ['pires.v1', 'pires.ticket.' + ('a' * 43)]},
                AsyncMock(),
                send,
            ))
        self.assertEqual(saidas, [{'type': 'websocket.close', 'code': 4401}])
        app.assert_not_awaited()
