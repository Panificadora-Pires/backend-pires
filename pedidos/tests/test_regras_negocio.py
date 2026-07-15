"""Testes de RN02, RN03, RN04 e permissões básicas de Pedido."""

from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from catalogo.models import Promocao
from pedidos.models import Pedido

from .base import CriaUsuariosEProdutosMixin


class CriarPedidoTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()

    def test_criar_pedido_reduz_estoque(self):
        """RN02 — o estoque deve ser reduzido no momento da criação do pedido."""
        self.client.force_authenticate(user=self.aluno)
        estoque_inicial = self.coxinha.estoque
        quantidade = 2
        resposta = self.client.post(
            '/api/pedidos/', {'itens_criacao': [{'produto': self.coxinha.id, 'quantidade': quantidade}]}, format='json'
        )

        assert resposta.status_code == status.HTTP_201_CREATED
        self.coxinha.refresh_from_db()
        assert self.coxinha.estoque == estoque_inicial - quantidade

    def test_criar_pedido_congela_preco_da_promocao(self):
        """O preço salvo no item deve ser o preco_atual no momento do pedido, não o preço-base."""
        Promocao.objects.create(
            produto=self.coxinha,
            preco_promocional=6.50,
            data_inicio=date.today() - timedelta(days=1),
            data_fim=date.today() + timedelta(days=1),
        )
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.post(
            '/api/pedidos/',
            {'itens_criacao': [{'produto': self.coxinha.id, 'quantidade': 1}]},
            format='json',
        )

        pedido = Pedido.objects.get(pk=resposta.data['id'])
        item = pedido.itens.get(produto=self.coxinha)
        assert str(item.preco_unitario) == '6.50'

    def test_criar_pedido_sem_estoque_suficiente_falha(self):
        """RN03 — não pode reservar mais do que o estoque disponível."""
        self.client.force_authenticate(user=self.aluno)
        estoque_inicial = self.suco.estoque
        resposta = self.client.post(
            '/api/pedidos/',
            {'itens_criacao': [{'produto': self.suco.id, 'quantidade': 999}]},
            format='json',
        )

        assert resposta.status_code == status.HTTP_400_BAD_REQUEST
        self.suco.refresh_from_db()
        assert self.suco.estoque == estoque_inicial, 'estoque não deveria ter sido alterado numa criação que falhou'

    def test_criar_pedido_sem_itens_falha(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.post('/api/pedidos/', {'itens_criacao': []}, format='json')
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST

    def test_aluno_nao_ve_pedido_de_outro_aluno(self):
        pedido = Pedido.objects.create(usuario=self.aluno)
        self.client.force_authenticate(user=self.outro_aluno)
        resposta = self.client.get(f'/api/pedidos/{pedido.id}/')
        assert resposta.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_ve_pedido_de_qualquer_aluno(self):
        pedido = Pedido.objects.create(usuario=self.aluno)
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(f'/api/pedidos/{pedido.id}/')
        assert resposta.status_code == status.HTTP_200_OK


class TransicaoStatusTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()
        self.pedido = Pedido.objects.create(usuario=self.aluno)

    def test_aluno_nao_pode_alterar_status(self):
        """Só a administração pode avançar o status do pedido."""
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.patch(
            f'/api/pedidos/{self.pedido.id}/alterar_status/', {'status': 'confirmado'}, format='json'
        )
        assert resposta.status_code == status.HTTP_403_FORBIDDEN

    def test_transicoes_validas_da_rn04(self):
        """RN04 — cada etapa só pode avançar para a próxima prevista."""
        self.client.force_authenticate(user=self.admin)
        sequencia = ['confirmado', 'pronto', 'retirado']

        for novo_status in sequencia:
            resposta = self.client.patch(
                f'/api/pedidos/{self.pedido.id}/alterar_status/', {'status': novo_status}, format='json'
            )
            assert resposta.status_code == status.HTTP_200_OK, f'falhou ao tentar ir para "{novo_status}"'

    def test_transicao_pulando_etapa_falha(self):
        """RN04 — pendente não pode ir direto para pronto."""
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.patch(
            f'/api/pedidos/{self.pedido.id}/alterar_status/', {'status': 'pronto'}, format='json'
        )
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST

    def test_transicao_a_partir_de_retirado_falha(self):
        """RN04 — status final não tem mais nenhuma transição possível."""
        self.pedido.status = Pedido.Status.RETIRADO
        self.pedido.save()
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.patch(
            f'/api/pedidos/{self.pedido.id}/alterar_status/', {'status': 'confirmado'}, format='json'
        )
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST

    def test_cancelar_a_partir_de_confirmado_e_permitido(self):
        self.pedido.status = Pedido.Status.CONFIRMADO
        self.pedido.save()
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.patch(
            f'/api/pedidos/{self.pedido.id}/alterar_status/', {'status': 'cancelado'}, format='json'
        )
        assert resposta.status_code == status.HTTP_200_OK
