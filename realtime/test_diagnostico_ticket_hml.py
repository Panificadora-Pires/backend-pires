"""Regressão HML: diferenciar 503 e testar ticket real sem compartilhar segredos."""
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from core.models import User
from realtime.tests import RedisFalso


HOST_HML = "backend-pires-hml.class.fabricadesoftware.ifc.edu.br"
DB_NEON = {"default": {"HOST": "ep-teste.sa-east-1.aws.neon.tech"}}


class DiagnosticarTicketHmlTests(SimpleTestCase):
    @override_settings(REALTIME_ENABLED=True)
    def test_emite_e_consumo_uma_vez_sem_vazar_ticket(self):
        redis = RedisFalso()
        saida = StringIO()
        with patch.object(settings, "ALLOWED_HOSTS", [HOST_HML]), patch.object(
            settings, "DATABASES", DB_NEON
        ), patch("realtime.tickets._client", return_value=redis):
            call_command("diagnosticar_ticket_hml", stdout=saida)
        self.assertIn("REALTIME_ENABLED efetivo no processo de comando: True", saida.getvalue())
        self.assertIn("Emissão de ticket Redis: OK", saida.getvalue())
        self.assertIn("Consumo único GETDEL do ticket: OK", saida.getvalue())
        self.assertNotIn("pires:realtime:ticket:", saida.getvalue())
        self.assertFalse(redis.dados)

    @override_settings(REALTIME_ENABLED=False)
    def test_realtime_falso_interrompe_diagnostico(self):
        with patch.object(settings, "ALLOWED_HOSTS", [HOST_HML]), patch.object(
            settings, "DATABASES", DB_NEON
        ):
            with self.assertRaisesMessage(CommandError, "Realtime desativado"):
                call_command("diagnosticar_ticket_hml", stdout=StringIO())

    @override_settings(REALTIME_ENABLED=True)
    def test_rejeita_host_de_producao(self):
        with patch.object(settings, "ALLOWED_HOSTS", [
            "backend-pires.class.fabricadesoftware.ifc.edu.br"
        ]), patch.object(settings, "DATABASES", DB_NEON):
            with self.assertRaisesMessage(CommandError, "Ambiente não é a homologação"):
                call_command("diagnosticar_ticket_hml", stdout=StringIO())

    @override_settings(REALTIME_ENABLED=True)
    def test_erro_sanitizado_sem_url_redis(self):
        with patch.object(settings, "ALLOWED_HOSTS", [HOST_HML]), patch.object(
            settings, "DATABASES", DB_NEON
        ), patch("realtime.tickets._client",
                 side_effect=OSError("redis://senha-nao-exibir@redis.local:6379")):
            with self.assertRaises(CommandError) as erro:
                call_command("diagnosticar_ticket_hml", stdout=StringIO())
        self.assertIn("OSError", str(erro.exception))
        self.assertNotIn("senha-nao-exibir", str(erro.exception))


class TicketHttpHmlLogsTests(APITestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            email="hml-teste@example.invalid",
            password="senha-super-segura-2026",
            is_active=True,
            email_verified=True,
        )
        self.client.force_authenticate(user=self.usuario)

    @override_settings(REALTIME_ENABLED=False)
    def test_http_503_desligado_registra_motivo_seguro(self):
        with self.assertLogs("realtime.views", level="WARNING") as logs:
            r = self.client.post("/api/realtime/ticket/")
        self.assertEqual(r.status_code, 503)
        self.assertIn("ticket_hml reason=realtime_disabled", "\n".join(logs.output))

    @override_settings(REALTIME_ENABLED=True)
    def test_http_503_redis_registra_classe_sem_senha(self):
        with patch("realtime.tickets._client",
                   side_effect=OSError("redis://senha-nao-exibir@host")):
            with self.assertLogs("realtime.views", level="WARNING") as logs:
                r = self.client.post("/api/realtime/ticket/")
        joined = "\n".join(logs.output)
        self.assertEqual(r.status_code, 503)
        self.assertIn("ticket_hml reason=emission_failed cause_type=OSError", joined)
        self.assertNotIn("senha-nao-exibir", joined)
        self.assertNotIn("senha-nao-exibir", str(r.data))
