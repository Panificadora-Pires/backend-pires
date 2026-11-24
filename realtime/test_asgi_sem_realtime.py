"""PR7C Fase A: o Procfile de produção usa ASGI com o realtime desligado."""
from asgiref.testing import ApplicationCommunicator
from django.core.handlers.asgi import ASGIHandler
from django.test import SimpleTestCase, override_settings


@override_settings(REALTIME_ENABLED=False)
class AsgiSemRealtimeTests(SimpleTestCase):
    databases = {'default'}

    def test_aplicacao_asgi_e_somente_http_sem_redis(self):
        from app.asgi import application

        self.assertIsInstance(application, ASGIHandler)

    async def test_health_responde_200_pelo_asgi(self):
        from app.asgi import application

        comunicador = ApplicationCommunicator(application, {
            'type': 'http',
            'asgi': {'version': '3.0'},
            'http_version': '1.1',
            'method': 'GET',
            'scheme': 'https',
            'path': '/api/health/',
            'raw_path': b'/api/health/',
            'query_string': b'',
            'root_path': '',
            'headers': [(b'host', b'localhost')],
            'client': ('127.0.0.1', 50000),
            'server': ('localhost', 443),
        })
        await comunicador.send_input({'type': 'http.request', 'body': b'', 'more_body': False})
        inicio = await comunicador.receive_output(timeout=10)
        await comunicador.receive_output(timeout=10)

        self.assertEqual(inicio['status'], 200)
