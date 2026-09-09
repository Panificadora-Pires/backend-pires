from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from pedidos.models import Pedido

from .base import CriaUsuariosEProdutosMixin


MP_SETTINGS = override_settings(
    MERCADO_PAGO_ACCESS_TOKEN='TEST-ACCESS-TOKEN',
    MERCADO_PAGO_API_BASE_URL='https://api.mercadopago.com',
    MERCADO_PAGO_TIMEOUT_SECONDS=5,
    MERCADO_PAGO_WEBHOOK_URL='',
    PAGAMENTO_TEMPO_LIMITE_MINUTOS=15,
)


@MP_SETTINGS
class CheckoutPagamentoTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()
        self.client.force_authenticate(user=self.aluno)

    def itens(self, quantidade=1):
        return [{'produto': self.coxinha.id, 'quantidade': quantidade}]

    def test_checkout_dinheiro_reserva_estoque(self):
        estoque = self.coxinha.estoque
        resposta = self.client.post(
            '/api/pedidos/checkout_dinheiro/',
            {'checkout_id': str(uuid4()), 'itens_criacao': self.itens(2)},
            format='json',
        )
        assert resposta.status_code == status.HTTP_201_CREATED
        pedido = Pedido.objects.get(pk=resposta.data['pedido']['id'])
        assert pedido.forma_pagamento == Pedido.FormaPagamento.DINHEIRO
        assert pedido.status_pagamento == Pedido.StatusPagamento.PENDENTE
        self.coxinha.refresh_from_db()
        assert self.coxinha.estoque == estoque - 2

    @patch('pedidos.services.pagamentos.requests.post')
    def test_cartao_aprovado_confirma_pedido(self, post):
        resposta_mp = Mock(status_code=201)
        resposta_mp.json.return_value = {
            'id': 123456,
            'status': 'approved',
            'status_detail': 'accredited',
            'payment_method_id': 'visa',
        }
        post.return_value = resposta_mp

        resposta = self.client.post(
            '/api/pedidos/checkout_mercado_pago/',
            {
                'checkout_id': str(uuid4()),
                'itens_criacao': self.itens(),
                'payment_type': 'credit_card',
                'form_data': {
                    'payment_method_id': 'visa',
                    'token': 'token-teste',
                    'installments': 1,
                    'payer': {'email': 'aluno@teste.com'},
                },
            },
            format='json',
        )
        assert resposta.status_code == status.HTTP_201_CREATED
        pedido = Pedido.objects.get(pk=resposta.data['pedido']['id'])
        assert pedido.forma_pagamento == Pedido.FormaPagamento.CARTAO
        assert pedido.status_pagamento == Pedido.StatusPagamento.APROVADO
        assert pedido.status == Pedido.Status.CONFIRMADO
        assert pedido.mercadopago_payment_id == '123456'

    @patch('pedidos.services.pagamentos.requests.post')
    def test_pix_pendente_retorna_qr_code(self, post):
        resposta_mp = Mock(status_code=201)
        resposta_mp.json.return_value = {
            'id': 999,
            'status': 'pending',
            'status_detail': 'pending_waiting_transfer',
            'payment_method_id': 'pix',
            'point_of_interaction': {
                'transaction_data': {
                    'qr_code': '000201PIXTESTE',
                    'qr_code_base64': 'ABC123',
                }
            },
        }
        post.return_value = resposta_mp

        resposta = self.client.post(
            '/api/pedidos/checkout_mercado_pago/',
            {
                'checkout_id': str(uuid4()),
                'itens_criacao': self.itens(),
                'payment_type': 'bank_transfer',
                'form_data': {
                    'payment_method_id': 'pix',
                    'payer': {
                        'email': 'aluno@teste.com',
                        'identification': {'type': 'CPF', 'number': '19119119100'},
                    },
                },
            },
            format='json',
        )
        assert resposta.status_code == status.HTTP_201_CREATED
        assert resposta.data['pagamento']['pix_qr_code'] == '000201PIXTESTE'
        pedido = Pedido.objects.get(pk=resposta.data['pedido']['id'])
        assert pedido.status_pagamento == Pedido.StatusPagamento.PENDENTE
        assert pedido.status == Pedido.Status.PENDENTE

    @patch('pedidos.services.pagamentos.requests.post')
    def test_pagamento_recusado_devolve_estoque(self, post):
        estoque = self.coxinha.estoque
        resposta_mp = Mock(status_code=201)
        resposta_mp.json.return_value = {
            'id': 555,
            'status': 'rejected',
            'status_detail': 'cc_rejected_other_reason',
            'payment_method_id': 'visa',
        }
        post.return_value = resposta_mp

        resposta = self.client.post(
            '/api/pedidos/checkout_mercado_pago/',
            {
                'checkout_id': str(uuid4()),
                'itens_criacao': self.itens(),
                'payment_type': 'credit_card',
                'form_data': {
                    'payment_method_id': 'visa',
                    'token': 'token-teste',
                    'installments': 1,
                    'payer': {'email': 'aluno@teste.com'},
                },
            },
            format='json',
        )
        assert resposta.status_code == status.HTTP_201_CREATED
        pedido = Pedido.objects.get(pk=resposta.data['pedido']['id'])
        assert pedido.status == Pedido.Status.CANCELADO
        assert pedido.status_pagamento == Pedido.StatusPagamento.RECUSADO
        assert pedido.estoque_devolvido
        self.coxinha.refresh_from_db()
        assert self.coxinha.estoque == estoque
