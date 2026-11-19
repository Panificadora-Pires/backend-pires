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

    @override_settings(REALTIME_ENABLED=True)
    def test_handshake_valido_entrega_apenas_escopo_autorizado(self):
        from types import SimpleNamespace
        from realtime.auth import TicketAuthMiddleware

        usuario = SimpleNamespace(pk=12, is_staff=False, is_authenticated=True)
        aplicativo = AsyncMock()
        middleware = TicketAuthMiddleware(aplicativo)
        with (
            patch('realtime.auth.consumir_ticket', return_value=(12, 'usuario')),
            patch('realtime.auth._conta_ativa', new_callable=AsyncMock, return_value=usuario),
        ):
            asyncio.run(middleware(
                {'type': 'websocket', 'subprotocols': ['pires.v1', 'pires.ticket.' + ('a' * 43)]},
                AsyncMock(),
                AsyncMock(),
            ))
        aplicativo.assert_awaited_once()
        escopo = aplicativo.await_args.args[0]
        self.assertEqual(escopo['user'], usuario)
        self.assertEqual(escopo['realtime_papel'], 'usuario')

    def test_origins_desconhecidas_sao_rejeitadas(self):
        from channels.security.websocket import OriginValidator

        app = AsyncMock()
        middleware = OriginValidator(app, ['https://frontend-pires.vercel.app'])
        saidas = []

        async def send(message):
            saidas.append(message)

        mensagens = iter((
            {'type': 'websocket.connect'},
            {'type': 'websocket.disconnect', 'code': 1000},
        ))

        async def receive():
            return next(mensagens)

        async def verificar():
            await asyncio.wait_for(
                middleware(
                    {
                        'type': 'websocket',
                        'headers': [(b'origin', b'https://site-malicioso.example')],
                        'subprotocols': [],
                    },
                    receive,
                    send,
                ),
                timeout=2,
            )

        asyncio.run(verificar())
        app.assert_not_awaited()
        self.assertTrue(any(item.get('type') == 'websocket.close' for item in saidas))

    def test_consumer_somente_leitura_separa_grupos_e_remove_payload_extra(self):
        from types import SimpleNamespace
        from realtime.consumers import EventsConsumer

        class CamadaFalsa:
            def __init__(self):
                self.adicionados = []
                self.removidos = []

            async def group_add(self, grupo, canal):
                self.adicionados.append((grupo, canal))

            async def group_discard(self, grupo, canal):
                self.removidos.append((grupo, canal))

        async def caso(papel, pk):
            usuario = SimpleNamespace(pk=pk, is_staff=(papel == 'admin'), is_authenticated=True)
            consumer = EventsConsumer()
            consumer.scope = {'user': usuario, 'realtime_papel': papel}
            consumer.channel_layer = CamadaFalsa()
            consumer.channel_name = 'canal-teste'
            consumer.accept = AsyncMock()
            consumer.close = AsyncMock()
            consumer.send = AsyncMock()
            await consumer.connect()
            grupo = 'pires-admin-eventos' if papel == 'admin' else f'pires-usuario-{pk}'
            self.assertEqual(consumer.channel_layer.adicionados, [(grupo, 'canal-teste')])
            consumer.accept.assert_awaited_once_with(subprotocol='pires.v1')
            await consumer.realtime_event({
                'payload': {
                    'v': 1, 'tipo': 'pedido.atualizado',
                    'pedido_id': 19, 'event_id': 'uuid',
                    'email': 'privado@example.com', 'token': 'segredo',
                },
            })
            dados = consumer.send.await_args.kwargs['text_data']
            self.assertNotIn('email', dados)
            self.assertNotIn('segredo', dados)
            consumer.send.reset_mock()
            await consumer.realtime_event({'payload': {'v': 2, 'tipo': 'nao.autorizado'}})
            consumer.send.assert_not_awaited()
            await consumer.receive(text_data='{"alterar_status": "pronto"}')
            consumer.close.assert_awaited_with(code=4403)
            await consumer.disconnect(1000)
            self.assertEqual(consumer.channel_layer.removidos, [(grupo, 'canal-teste')])

        asyncio.run(caso('admin', 2))
        asyncio.run(caso('usuario', 3))
