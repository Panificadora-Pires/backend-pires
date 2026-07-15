"""Testes do QR Code de retirada e da notificação (signal pedido_ficou_pronto)."""

from rest_framework import status
from rest_framework.test import APITestCase

from notificacoes.models import Notificacao
from pedidos.models import Pedido

from .base import CriaUsuariosEProdutosMixin


class QRCodeRetiradaTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()
        self.pedido = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.PRONTO)

    def test_obter_qrcode(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get(f'/api/pedidos/{self.pedido.id}/qrcode/')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['codigo_retirada'], str(self.pedido.codigo_retirada))
        self.assertTrue(resposta.data['qrcode_base64'].startswith('data:image/png;base64,'))

    def test_admin_retira_pedido_pronto(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': str(self.pedido.codigo_retirada)},
            format='json',
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, Pedido.Status.RETIRADO)

    def test_retirar_pedido_ja_retirado_falha(self):
        self.pedido.status = Pedido.Status.RETIRADO
        self.pedido.save()
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': str(self.pedido.codigo_retirada)},
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retirar_pedido_ainda_nao_pronto_falha(self):
        self.pedido.status = Pedido.Status.PENDENTE
        self.pedido.save()
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': str(self.pedido.codigo_retirada)},
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_aluno_nao_pode_retirar_via_qrcode(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': str(self.pedido.codigo_retirada)},
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_codigo_invalido_falha(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': '00000000-0000-0000-0000-000000000000'},
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)


class NotificacaoPedidoProntoTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()
        self.pedido = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.CONFIRMADO)

    def test_notificacao_criada_ao_ficar_pronto(self):
        self.assertEqual(Notificacao.objects.filter(usuario=self.aluno).count(), 0)

        self.client.force_authenticate(user=self.admin)
        self.client.patch(f'/api/pedidos/{self.pedido.id}/alterar_status/', {'status': 'pronto'}, format='json')

        notificacoes = Notificacao.objects.filter(usuario=self.aluno)
        self.assertEqual(notificacoes.count(), 1)
        self.assertIn(str(self.pedido.id), notificacoes.first().mensagem)

    def test_notificacao_nao_duplica_se_status_ja_era_pronto(self):
        self.pedido.status = Pedido.Status.PRONTO
        self.pedido.save()

        self.client.force_authenticate(user=self.admin)
        # tenta "reafirmar" pronto -> RN04 nem deveria permitir (pronto não transiciona pra pronto)
        self.client.patch(f'/api/pedidos/{self.pedido.id}/alterar_status/', {'status': 'pronto'}, format='json')

        self.assertEqual(Notificacao.objects.filter(usuario=self.aluno).count(), 0)

    def test_marcar_notificacao_como_lida(self):
        notificacao = Notificacao.objects.create(usuario=self.aluno, pedido=self.pedido, mensagem='teste')
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.patch(f'/api/notificacoes/{notificacao.id}/marcar_lida/')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        notificacao.refresh_from_db()
        self.assertTrue(notificacao.lida)

    def test_aluno_nao_ve_notificacao_de_outro(self):
        notificacao = Notificacao.objects.create(usuario=self.aluno, pedido=self.pedido, mensagem='teste')
        self.client.force_authenticate(user=self.outro_aluno)
        resposta = self.client.get('/api/notificacoes/')

        ids_retornados = [n['id'] for n in resposta.data['results']]
        self.assertNotIn(notificacao.id, ids_retornados)
