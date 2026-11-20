"""Gates do diagnóstico Redis no Fabroku, sem conexão externa nos testes."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class DiagnosticarRedisHmlTests(SimpleTestCase):
    @override_settings(REALTIME_REDIS_URL="")
    def test_ausencia_de_redis_falha_sem_exibir_configuracao(self):
        with self.assertRaisesMessage(CommandError, "Redis HML não configurado"):
            call_command("diagnosticar_redis_hml", stdout=StringIO())

    @override_settings(REALTIME_REDIS_URL="redis://hml.example:6379/0")
    @patch("redis.Redis.from_url")
    def test_valida_ping_info_getdel_sem_expor_endereco(self, criar):
        cliente = criar.return_value
        cliente.ping.return_value = True
        cliente.info.return_value = {"redis_version": "7.4.2"}
        cliente.set.return_value = True
        cliente.getdel.side_effect = ["hml", None]
        saida = StringIO()

        call_command("diagnosticar_redis_hml", stdout=saida)

        self.assertIn("Redis PING: OK", saida.getvalue())
        self.assertIn("GETDEL atômico: OK", saida.getvalue())
        self.assertIn("7.4.2", saida.getvalue())
        self.assertNotIn("hml.example", saida.getvalue())
        self.assertEqual(cliente.getdel.call_count, 2)
        self.assertEqual(cliente.set.call_args.kwargs["ex"], 30)
        cliente.close.assert_called_once()

    @override_settings(REALTIME_REDIS_URL="redis://hml.example:6379/0")
    @patch("redis.Redis.from_url")
    def test_getdel_nao_suportado_falha_sem_credenciais(self, criar):
        from redis.exceptions import ResponseError

        cliente = criar.return_value
        cliente.set.return_value = True
        cliente.info.return_value = {"redis_version": "6.0.0"}
        cliente.getdel.side_effect = ResponseError("unknown command 'GETDEL'")
        with self.assertRaises(CommandError) as erro:
            call_command("diagnosticar_redis_hml", stdout=StringIO())
        self.assertIn("Falha de conectividade", str(erro.exception))
        self.assertNotIn("hml.example", str(erro.exception))
