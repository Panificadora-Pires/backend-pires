"""Testes do relatório de vendas (RF11) e produtos mais vendidos (RF12)."""

from datetime import date

from rest_framework import status
from rest_framework.test import APITestCase

from pedidos.models import ItemPedido, Pedido

from .base import CriaUsuariosEProdutosMixin


class RelatorioVendasTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()

        # pedido retirado hoje: 2 coxinhas a R$8 = R$16
        pedido = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.RETIRADO)
        ItemPedido.objects.create(pedido=pedido, produto=self.coxinha, quantidade=2, preco_unitario=8)

        # pedido ainda pendente não deve contar no relatório
        pedido_pendente = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.PENDENTE)
        ItemPedido.objects.create(pedido=pedido_pendente, produto=self.coxinha, quantidade=5, preco_unitario=8)

        self.hoje = date.today().isoformat()

    def test_requer_autenticacao_de_admin(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get(f'/api/pedidos/relatorio_vendas/?data_inicio={self.hoje}&data_fim={self.hoje}')
        assert resposta.status_code == status.HTTP_403_FORBIDDEN

    def test_exige_parametros_de_data(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get('/api/pedidos/relatorio_vendas/')
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST

    def test_data_invalida(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get('/api/pedidos/relatorio_vendas/?data_inicio=31-12-2025&data_fim=hoje')
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST

    def test_calcula_apenas_pedidos_retirados(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(f'/api/pedidos/relatorio_vendas/?data_inicio={self.hoje}&data_fim={self.hoje}')

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data['total_pedidos'] == 1
        assert str(resposta.data['total_vendido']) == '16.00'
        assert str(resposta.data['ticket_medio']) == '16.00'

    def test_periodo_sem_vendas_nao_quebra(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get('/api/pedidos/relatorio_vendas/?data_inicio=2020-01-01&data_fim=2020-01-31')

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data['total_pedidos'] == 0
        assert str(resposta.data['total_vendido']) == '0.00'


class ProdutosMaisVendidosTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()
        self.quantidade_coxinha_vendida = 8

        pedido1 = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.RETIRADO)
        ItemPedido.objects.create(pedido=pedido1, produto=self.coxinha, quantidade=5, preco_unitario=8)
        ItemPedido.objects.create(pedido=pedido1, produto=self.suco, quantidade=1, preco_unitario=6)

        pedido2 = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.RETIRADO)
        ItemPedido.objects.create(pedido=pedido2, produto=self.coxinha, quantidade=3, preco_unitario=8)

        # pedido cancelado não deve contar no ranking
        pedido_cancelado = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.CANCELADO)
        ItemPedido.objects.create(pedido=pedido_cancelado, produto=self.suco, quantidade=50, preco_unitario=6)

    def test_requer_admin(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get('/api/produtos/mais_vendidos/')
        assert resposta.status_code == status.HTTP_403_FORBIDDEN

    def test_ranking_correto_e_ordenado(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get('/api/produtos/mais_vendidos/')

        assert resposta.status_code == status.HTTP_200_OK
        resultado = resposta.data['resultado']
        assert resultado[0]['produto_nome'] == 'Coxinha de frango'
        assert resultado[0]['quantidade_vendida'] == self.quantidade_coxinha_vendida  # 5 + 3, ignora o pedido cancelado
        assert resultado[1]['produto_nome'] == 'Suco de laranja'
        assert resultado[1]['quantidade_vendida'] == 1

    def test_respeita_limite(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get('/api/produtos/mais_vendidos/?limite=1')
        assert len(resposta.data['resultado']) == 1
