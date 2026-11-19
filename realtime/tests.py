"""Regressões REST e segurança dos tickets PR6A.1 (sem Redis externo)."""
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from core.models import User
from realtime.tickets import TicketUnavailable, consumir_ticket, emitir_ticket


class RedisFalso:
    def __init__(self):
        self.dados = {}
        self.ttls = []

    def set(self, chave, valor, ex, nx):
        if nx and chave in self.dados:
            return False
        self.dados[chave] = valor
        self.ttls.append(ex)
        return True

    def getdel(self, chave):
        return self.dados.pop(chave, None)


class TicketSegurancaTestCase(APITestCase):
    def setUp(self):
        self.cliente = User.objects.create_user(
            email='cliente-ws@example.com', password='SenhaForte123',
            is_active=True, email_verified=True,
        )
        self.admin = User.objects.create_user(
            email='admin-ws@example.com', password='SenhaForte123',
            is_staff=True, is_active=True, email_verified=True,
        )
        self.redis = RedisFalso()
        self.url = reverse('realtime-ticket')

    def test_recurso_desligado_por_padrao_nao_emite_ticket(self):
        self.client.force_authenticate(user=self.admin)
        with override_settings(REALTIME_ENABLED=False):
            self.assertEqual(self.client.post(self.url).status_code, 503)

    def test_anonimo_nao_recebe_ticket_quando_habilitado(self):
        with override_settings(REALTIME_ENABLED=True):
            self.assertIn(self.client.post(self.url).status_code, (401, 403))

    @override_settings(REALTIME_ENABLED=True, REALTIME_TICKET_TTL_SECONDS=45)
    def test_cliente_e_admin_recebem_apenas_suas_permissoes(self):
        with patch('realtime.tickets._client', return_value=self.redis):
            for usuario, papel in ((self.cliente, 'usuario'), (self.admin, 'admin')):
                self.client.force_authenticate(user=usuario)
                resposta = self.client.post(self.url)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.data['expires_in'], 45)
                self.assertEqual(resposta.data['ws_path'], '/ws/v1/events/')
                self.assertEqual(resposta.data['protocol'], 'pires.v1')
                self.assertEqual(resposta['Cache-Control'], 'no-store')
                ticket = resposta.data['ticket']
                self.assertEqual(consumir_ticket(ticket), (usuario.pk, papel))
                self.assertIsNone(consumir_ticket(ticket))
                self.assertEqual(len(ticket), 43)
            self.assertEqual(self.redis.ttls, [45, 45])
            # Redis guarda somente hash do ticket, nunca o segredo bruto.
            self.assertTrue(all(chave.startswith('pires:realtime:ticket:') for chave in self.redis.dados))

    @override_settings(REALTIME_ENABLED=True)
    def test_tickets_invalidos_nao_geram_consulta_no_redis(self):
        with patch('realtime.tickets._client', side_effect=AssertionError('Redis não deveria ser chamado')):
            for ticket in ('', 'abc', '../../etc', 'a' * 129, None):
                self.assertIsNone(consumir_ticket(ticket))

    @override_settings(REALTIME_ENABLED=True, REALTIME_TICKET_TTL_SECONDS=45)
    def test_uso_unico_e_expiracao_fecham_acesso(self):
        with patch('realtime.tickets._client', return_value=self.redis):
            ticket = emitir_ticket(self.cliente)
            # Simula TTL expirado no Redis, sem esperar 45 segundos.
            self.redis.dados.clear()
            self.assertIsNone(consumir_ticket(ticket))
            ticket = emitir_ticket(self.admin)
            self.assertEqual(consumir_ticket(ticket), (self.admin.pk, 'admin'))
            self.assertIsNone(consumir_ticket(ticket))

    @override_settings(REALTIME_ENABLED=True)
    def test_usuario_inativo_nao_pode_emitir(self):
        self.cliente.is_active = False
        self.cliente.save(update_fields=['is_active'])
        with self.assertRaises(TicketUnavailable):
            emitir_ticket(self.cliente)

    @override_settings(REALTIME_ENABLED=True)
    def test_falha_de_redis_retorna_503_sem_vazar_informacoes(self):
        self.client.force_authenticate(user=self.admin)
        with patch('realtime.tickets._client', side_effect=OSError('senha-redis-sigilo')):
            resposta = self.client.post(self.url)
        self.assertEqual(resposta.status_code, 503)
        self.assertNotIn('senha-redis-sigilo', str(resposta.data))
