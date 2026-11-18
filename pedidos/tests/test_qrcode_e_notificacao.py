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

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data['codigo_retirada'] == str(self.pedido.codigo_retirada)
        assert resposta.data['qrcode_base64'].startswith('data:image/png;base64,')

    def test_admin_nao_recebe_codigo_na_lista_nem_no_detalhe(self):
        self.client.force_authenticate(user=self.admin)
        for rota in ('/api/pedidos/', f'/api/pedidos/{self.pedido.id}/'):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, status.HTTP_200_OK)
                dados = resposta.data['results'][0] if rota.endswith('/') and rota == '/api/pedidos/' else resposta.data
                self.assertNotIn('codigo_retirada', dados)

    def test_admin_nao_pode_solicitar_qrcode_de_cliente(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(f'/api/pedidos/{self.pedido.id}/qrcode/')
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_outro_cliente_nao_pode_obter_codigo_por_id(self):
        self.client.force_authenticate(user=self.outro_aluno)
        resposta = self.client.get(f'/api/pedidos/{self.pedido.id}/qrcode/')
        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)

    def test_cliente_recebe_codigo_no_checkout_tradicional(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.post(
            '/api/pedidos/',
            {'itens_criacao': [{'produto': self.coxinha.id, 'quantidade': 1}]},
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertIn('codigo_retirada', resposta.data)
        self.assertTrue(resposta.data['codigo_retirada'])

    def test_aluno_consegue_obter_codigo_no_detalhe(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get(f'/api/pedidos/{self.pedido.id}/')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['codigo_retirada'], str(self.pedido.codigo_retirada))

    def test_django_admin_nao_exibe_codigo_em_formulario_ou_busca(self):
        from pedidos.admin import PedidoAdmin
        self.assertIn('codigo_retirada', PedidoAdmin.exclude)
        self.assertNotIn('codigo_retirada', PedidoAdmin.search_fields)
        self.assertNotIn('codigo_retirada', PedidoAdmin.readonly_fields)

    def test_retirada_admin_nao_devolve_codigo_de_cliente(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': str(self.pedido.codigo_retirada)},
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertNotIn('codigo_retirada', resposta.data)

    def test_admin_retira_pedido_pronto(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': str(self.pedido.codigo_retirada)},
            format='json',
        )

        assert resposta.status_code == status.HTTP_200_OK
        self.pedido.refresh_from_db()
        assert self.pedido.status == Pedido.Status.RETIRADO

    def test_retirar_pedido_ja_retirado_falha(self):
        self.pedido.status = Pedido.Status.RETIRADO
        self.pedido.save()
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': str(self.pedido.codigo_retirada)},
            format='json',
        )
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST

    def test_retirar_pedido_ainda_nao_pronto_falha(self):
        self.pedido.status = Pedido.Status.PENDENTE
        self.pedido.save()
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': str(self.pedido.codigo_retirada)},
            format='json',
        )
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST

    def test_aluno_nao_pode_retirar_via_qrcode(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': str(self.pedido.codigo_retirada)},
            format='json',
        )
        assert resposta.status_code == status.HTTP_403_FORBIDDEN

    def test_codigo_invalido_falha(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': '00000000-0000-0000-0000-000000000000'},
            format='json',
        )
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST


class NotificacaoPedidoProntoTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()
        self.pedido = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.CONFIRMADO)

    def test_notificacao_criada_ao_ficar_pronto(self):
        assert Notificacao.objects.filter(usuario=self.aluno).count() == 0

        self.client.force_authenticate(user=self.admin)
        self.client.patch(f'/api/pedidos/{self.pedido.id}/alterar_status/', {'status': 'pronto'}, format='json')

        notificacoes = Notificacao.objects.filter(usuario=self.aluno)
        assert notificacoes.count() == 1
        assert str(self.pedido.id) in notificacoes.first().mensagem

    def test_notificacao_nao_duplica_se_status_ja_era_pronto(self):
        self.pedido.status = Pedido.Status.PRONTO
        self.pedido.save()

        self.client.force_authenticate(user=self.admin)
        # tenta "reafirmar" pronto -> RN04 nem deveria permitir (pronto não transiciona pra pronto)
        self.client.patch(f'/api/pedidos/{self.pedido.id}/alterar_status/', {'status': 'pronto'}, format='json')

        assert Notificacao.objects.filter(usuario=self.aluno).count() == 0

    def test_marcar_notificacao_como_lida(self):
        notificacao = Notificacao.objects.create(usuario=self.aluno, pedido=self.pedido, mensagem='teste')
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.patch(f'/api/notificacoes/{notificacao.id}/marcar_lida/')

        assert resposta.status_code == status.HTTP_200_OK
        notificacao.refresh_from_db()
        assert notificacao.lida

    def test_aluno_nao_ve_notificacao_de_outro(self):
        notificacao = Notificacao.objects.create(usuario=self.aluno, pedido=self.pedido, mensagem='teste')
        self.client.force_authenticate(user=self.outro_aluno)
        resposta = self.client.get('/api/notificacoes/')

        ids_retornados = [n['id'] for n in resposta.data['results']]
        assert notificacao.id not in ids_retornados
