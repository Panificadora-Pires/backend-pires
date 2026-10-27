"""Testes da expiração via serviço/endpoint, limites anti-abuso, paginação e health check."""

import uuid
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from pedidos.models import ItemPedido, Pedido
from pedidos.services.expiracao import expirar_pedidos

from .base import CriaUsuariosEProdutosMixin

URL_EXPIRAR = '/api/manutencao/expirar-pedidos/'


class ExpiracaoDePedidosTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()

    def _pedido(self, *, status_pedido, minutos_no_status, quantidade=2, **extra):
        pedido = Pedido.objects.create(usuario=self.aluno, status=status_pedido, **extra)
        ItemPedido.objects.create(
            pedido=pedido, produto=self.coxinha, quantidade=quantidade, preco_unitario=self.coxinha.preco
        )
        self.coxinha.estoque -= quantidade
        self.coxinha.save(update_fields=['estoque'])
        Pedido.objects.filter(pk=pedido.pk).update(
            status_atualizado_em=timezone.now() - timedelta(minutes=minutos_no_status)
        )
        return pedido

    def test_confirmado_parado_nao_e_cancelado_por_padrao(self):
        pedido = self._pedido(status_pedido=Pedido.Status.CONFIRMADO, minutos_no_status=60 * 48)

        resultado = expirar_pedidos()

        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.CONFIRMADO
        assert resultado.cancelados_preparo == 0

    @override_settings(PEDIDO_TEMPO_LIMITE_PREPARO_HORAS=24)
    def test_confirmado_parado_e_cancelado_quando_a_regra_esta_ligada(self):
        estoque_antes = self.coxinha.estoque
        pedido = self._pedido(status_pedido=Pedido.Status.CONFIRMADO, minutos_no_status=60 * 30, quantidade=3)

        resultado = expirar_pedidos()

        pedido.refresh_from_db()
        self.coxinha.refresh_from_db()
        assert pedido.status == Pedido.Status.CANCELADO
        assert resultado.cancelados_preparo == 1
        assert self.coxinha.estoque == estoque_antes

    @override_settings(PEDIDO_TEMPO_LIMITE_PREPARO_HORAS=24)
    def test_confirmado_recente_nao_e_cancelado(self):
        pedido = self._pedido(status_pedido=Pedido.Status.CONFIRMADO, minutos_no_status=60 * 2)

        expirar_pedidos()

        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.CONFIRMADO

    def test_pix_antigo_sem_order_fica_para_conciliacao_e_nao_devolve_estoque(self):
        """Sem ID de order o estado financeiro é incerto: não cancela nem libera estoque."""
        estoque_antes = self.coxinha.estoque
        pedido = self._pedido(
            status_pedido=Pedido.Status.PENDENTE,
            minutos_no_status=60 * 24 * 30,
            forma_pagamento=Pedido.FormaPagamento.PIX,
            status_pagamento=Pedido.StatusPagamento.PENDENTE,
        )
        Pedido.objects.filter(pk=pedido.pk).update(data=timezone.now() - timedelta(days=30))

        resultado = expirar_pedidos()

        pedido.refresh_from_db()
        self.coxinha.refresh_from_db()
        assert pedido.status == Pedido.Status.PENDENTE
        assert resultado.ignorados_por_falha == 1
        assert self.coxinha.estoque == estoque_antes - 2

    def test_pedido_em_dinheiro_pendente_nao_expira(self):
        pedido = self._pedido(status_pedido=Pedido.Status.PENDENTE, minutos_no_status=60 * 24 * 10)

        expirar_pedidos()

        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.PENDENTE


class EndpointDeManutencaoTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()

    @override_settings(MANUTENCAO_TOKEN='')
    def test_sem_token_configurado_o_endpoint_fica_desativado(self):
        resposta = self.client.post(URL_EXPIRAR, HTTP_X_MANUTENCAO_TOKEN='qualquer')
        assert resposta.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    @override_settings(MANUTENCAO_TOKEN='segredo-de-teste')
    def test_token_incorreto_e_rejeitado(self):
        resposta = self.client.post(URL_EXPIRAR, HTTP_X_MANUTENCAO_TOKEN='errado')
        assert resposta.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(MANUTENCAO_TOKEN='segredo-de-teste')
    def test_sem_cabecalho_e_rejeitado(self):
        resposta = self.client.post(URL_EXPIRAR)
        assert resposta.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(MANUTENCAO_TOKEN='segredo-de-teste')
    def test_usuario_logado_sem_token_de_manutencao_nao_executa(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(URL_EXPIRAR)
        assert resposta.status_code == status.HTTP_401_UNAUTHORIZED

    @override_settings(MANUTENCAO_TOKEN='segredo-de-teste')
    def test_token_correto_executa_a_expiracao(self):
        pedido = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.PRONTO)
        ItemPedido.objects.create(
            pedido=pedido, produto=self.coxinha, quantidade=1, preco_unitario=self.coxinha.preco
        )
        Pedido.objects.filter(pk=pedido.pk).update(status_atualizado_em=timezone.now() - timedelta(minutes=60))

        resposta = self.client.post(URL_EXPIRAR, HTTP_X_MANUTENCAO_TOKEN='segredo-de-teste')

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data['cancelados_retirada'] == 1
        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.CANCELADO

    @override_settings(MANUTENCAO_TOKEN='segredo-de-teste')
    def test_get_nao_e_permitido(self):
        resposta = self.client.get(URL_EXPIRAR, HTTP_X_MANUTENCAO_TOKEN='segredo-de-teste')
        assert resposta.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class HealthCheckTestCase(APITestCase):
    def test_health_responde_ok_sem_autenticacao(self):
        resposta = self.client.get('/api/health/')
        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data == {'status': 'ok'}


class LimitesDeCheckoutTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()
        self.client.force_authenticate(user=self.aluno)

    def _checkout_dinheiro(self, itens):
        return self.client.post(
            '/api/pedidos/checkout_dinheiro/',
            {'checkout_id': str(uuid.uuid4()), 'itens_criacao': itens},
            format='json',
        )

    @override_settings(PEDIDO_QUANTIDADE_MAXIMA_POR_ITEM=3)
    def test_quantidade_acima_do_maximo_e_recusada(self):
        resposta = self._checkout_dinheiro([{'produto': self.coxinha.id, 'quantidade': 4}])

        assert resposta.status_code == status.HTTP_400_BAD_REQUEST
        self.coxinha.refresh_from_db()
        assert self.coxinha.estoque == 10

    @override_settings(PEDIDO_MAXIMO_ITENS_DIFERENTES=1)
    def test_muitos_produtos_diferentes_sao_recusados(self):
        resposta = self._checkout_dinheiro(
            [
                {'produto': self.coxinha.id, 'quantidade': 1},
                {'produto': self.suco.id, 'quantidade': 1},
            ]
        )
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(PEDIDO_MAXIMO_PENDENTES_POR_USUARIO=2)
    def test_limite_de_pedidos_pendentes_por_usuario(self):
        for _ in range(2):
            resposta = self._checkout_dinheiro([{'produto': self.coxinha.id, 'quantidade': 1}])
            assert resposta.status_code == status.HTTP_201_CREATED

        resposta = self._checkout_dinheiro([{'produto': self.coxinha.id, 'quantidade': 1}])

        assert resposta.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in resposta.data
        self.coxinha.refresh_from_db()
        assert self.coxinha.estoque == 8

    @override_settings(PEDIDO_MAXIMO_PENDENTES_POR_USUARIO=2)
    def test_reenvio_do_mesmo_checkout_nao_conta_como_novo_pedido(self):
        checkout_id = str(uuid.uuid4())
        corpo = {'checkout_id': checkout_id, 'itens_criacao': [{'produto': self.coxinha.id, 'quantidade': 1}]}

        primeira = self.client.post('/api/pedidos/checkout_dinheiro/', corpo, format='json')
        segunda = self.client.post('/api/pedidos/checkout_dinheiro/', corpo, format='json')

        assert primeira.status_code == status.HTTP_201_CREATED
        assert segunda.status_code == status.HTTP_200_OK
        assert Pedido.objects.filter(usuario=self.aluno).count() == 1

    @override_settings(PEDIDO_MAXIMO_PENDENTES_POR_USUARIO=1)
    def test_limite_nao_afeta_outro_usuario(self):
        self._checkout_dinheiro([{'produto': self.coxinha.id, 'quantidade': 1}])

        self.client.force_authenticate(user=self.outro_aluno)
        resposta = self._checkout_dinheiro([{'produto': self.coxinha.id, 'quantidade': 1}])

        assert resposta.status_code == status.HTTP_201_CREATED


class PaginacaoTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()

    def test_resposta_traz_count_next_e_previous(self):
        for _ in range(3):
            Pedido.objects.create(usuario=self.aluno)
        self.client.force_authenticate(user=self.admin)

        primeira = self.client.get('/api/pedidos/', {'page_size': 2})
        segunda = self.client.get('/api/pedidos/', {'page_size': 2, 'page': 2})

        assert primeira.data['count'] == 3
        assert primeira.data['total_pages'] == 2
        assert primeira.data['previous'] is None
        assert 'page=2' in primeira.data['next']
        assert segunda.data['next'] is None
        assert 'page=1' in segunda.data['previous'] or segunda.data['previous'].endswith('page_size=2')
        assert len(segunda.data['results']) == 1

    def test_listagem_exige_autenticacao_por_padrao(self):
        resposta = self.client.get('/api/pedidos/')
        assert resposta.status_code == status.HTTP_401_UNAUTHORIZED
