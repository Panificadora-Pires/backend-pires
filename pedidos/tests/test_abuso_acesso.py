"""PR7A.3 (R-09): isolamento entre clientes e bloqueio de rotas administrativas."""
from rest_framework import status
from rest_framework.test import APITestCase

from chat.models import Conversa
from notificacoes.models import Notificacao
from pedidos.models import Pedido

from .base import CriaUsuariosEProdutosMixin


class AcessoEntreClientesTests(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()
        self.pedido = Pedido.objects.create(usuario=self.aluno)
        self.notificacao = Notificacao.objects.create(usuario=self.aluno, pedido=self.pedido, mensagem='teste')
        self.client.force_authenticate(user=self.outro_aluno)

    def test_outro_cliente_nao_acessa_pedido_alheio(self):
        for rota in (
            f'/api/pedidos/{self.pedido.id}/',
            f'/api/pedidos/{self.pedido.id}/pagamento/',
            f'/api/pedidos/{self.pedido.id}/qrcode/',
        ):
            with self.subTest(rota=rota):
                self.assertIn(
                    self.client.get(rota).status_code,
                    (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
                )

    def test_outro_cliente_nao_le_nem_marca_notificacao_alheia(self):
        self.assertEqual(
            self.client.get(f'/api/notificacoes/{self.notificacao.id}/').status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.patch(f'/api/notificacoes/{self.notificacao.id}/marcar_lida/').status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.client.post('/api/notificacoes/marcar_todas_lidas/')
        self.notificacao.refresh_from_db()
        self.assertFalse(self.notificacao.lida)

    def test_outro_cliente_nao_le_chat_alheio(self):
        Conversa.objects.get_or_create(pedido=self.pedido)
        self.assertIn(
            self.client.get(f'/api/chat/{self.pedido.id}/').status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

    def test_cliente_nao_le_dados_de_outro_usuario(self):
        self.assertEqual(self.client.get(f'/api/usuarios/{self.aluno.id}/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get('/api/usuarios/').status_code, status.HTTP_403_FORBIDDEN)

    def test_cliente_nao_retira_pedido_alheio_pelo_qrcode(self):
        resposta = self.client.post(
            '/api/pedidos/retirar_via_qrcode/',
            {'codigo_retirada': str(self.pedido.codigo_retirada)},
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.pedido.refresh_from_db()
        self.assertNotEqual(self.pedido.status, Pedido.Status.RETIRADO)


class RotasAdministrativasTests(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()
        self.pedido = Pedido.objects.create(usuario=self.aluno)
        self.client.force_authenticate(user=self.aluno)

    def test_cliente_recebe_403_em_rotas_administrativas(self):
        rotas = [
            ('get', '/api/usuarios/admin_listagem/'),
            ('get', '/api/usuarios/resumo_admin/'),
            ('get', '/api/pedidos/resumo_admin/'),
            ('get', '/api/pedidos/relatorio_vendas/'),
            ('get', '/api/pedidos/relatorio_analitico_admin/'),
            ('get', '/api/produtos/admin_catalogo/'),
            ('get', '/api/produtos/resumo_admin/'),
            ('get', f'/api/produtos/{self.coxinha.id}/admin_detalhe/'),
            ('get', '/api/categorias/admin_listagem/'),
            ('get', '/api/categorias/resumo_admin/'),
            ('get', '/api/promocoes/admin_listagem/'),
            ('get', '/api/promocoes/resumo_admin/'),
            ('post', '/api/produtos/'),
            ('post', '/api/categorias/'),
            ('post', '/api/promocoes/'),
            ('post', '/api/admin-convites/'),
            ('patch', f'/api/pedidos/{self.pedido.id}/alterar_status/'),
            ('patch', f'/api/produtos/{self.coxinha.id}/'),
            ('delete', f'/api/produtos/{self.coxinha.id}/'),
        ]
        for metodo, rota in rotas:
            with self.subTest(metodo=metodo, rota=rota):
                resposta = getattr(self.client, metodo)(rota, {}, format='json')
                self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_cliente_nao_altera_status_do_proprio_pedido(self):
        resposta = self.client.patch(
            f'/api/pedidos/{self.pedido.id}/alterar_status/', {'status': 'confirmado'}, format='json'
        )
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, Pedido.Status.PENDENTE)
