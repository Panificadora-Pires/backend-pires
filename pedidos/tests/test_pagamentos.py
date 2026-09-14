import hashlib
import hmac
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
    MERCADO_PAGO_SANDBOX=True,
    MERCADO_PAGO_WEBHOOK_URL='',
    MERCADO_PAGO_WEBHOOK_SECRET='segredo-teste',
    PAGAMENTO_TEMPO_LIMITE_MINUTOS=45,
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
    def test_cartao_aprovado_cria_order_e_confirma_pedido(self, post):
        resposta_mp = Mock(status_code=201)
        resposta_mp.json.return_value = {
            'id': 'ORD01TESTCARD',
            'status': 'processed',
            'status_detail': 'accredited',
            'external_reference': '1',
            'transactions': {
                'payments': [
                    {
                        'id': 'PAY01TESTCARD',
                        'status': 'processed',
                        'status_detail': 'accredited',
                        'payment_method': {
                            'id': 'visa',
                            'type': 'credit_card',
                            'installments': 1,
                        },
                    }
                ]
            },
        }
        post.return_value = resposta_mp

        checkout_id = str(uuid4())
        resposta = self.client.post(
            '/api/pedidos/checkout_mercado_pago/',
            {
                'checkout_id': checkout_id,
                'itens_criacao': self.itens(),
                'payment_type': 'credit_card',
                'form_data': {
                    'transaction_amount': 8,
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
        assert pedido.mercadopago_order_id == 'ORD01TESTCARD'
        assert pedido.mercadopago_payment_id == 'PAY01TESTCARD'

        args, kwargs = post.call_args
        assert args[0] == 'https://api.mercadopago.com/v1/orders'
        assert kwargs['headers']['X-Idempotency-Key'] == checkout_id
        payload = kwargs['json']
        assert payload['processing_mode'] == 'automatic'
        assert payload['total_amount'] == '8.00'
        assert payload['payer']['email'] == 'test@testuser.com'
        metodo = payload['transactions']['payments'][0]['payment_method']
        assert metodo['token'] == 'token-teste'
        assert metodo['type'] == 'credit_card'
        assert payload['config']['online']['transaction_security']['validation'] == 'on_fraud_risk'

    @patch('pedidos.services.pagamentos.requests.post')
    def test_pix_pendente_retorna_qr_code_da_order(self, post):
        resposta_mp = Mock(status_code=201)
        resposta_mp.json.return_value = {
            'id': 'ORD01TESTPIX',
            'status': 'action_required',
            'status_detail': 'waiting_transfer',
            'transactions': {
                'payments': [
                    {
                        'id': 'PAY01TESTPIX',
                        'status': 'action_required',
                        'status_detail': 'waiting_transfer',
                        'payment_method': {
                            'id': 'pix',
                            'type': 'bank_transfer',
                            'qr_code': '000201PIXTESTE',
                            'qr_code_base64': 'ABC123',
                        },
                    }
                ]
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
                    'payer': {'email': 'aluno@teste.com'},
                },
            },
            format='json',
        )

        assert resposta.status_code == status.HTTP_201_CREATED
        assert resposta.data['pagamento']['pix_qr_code'] == '000201PIXTESTE'
        pedido = Pedido.objects.get(pk=resposta.data['pedido']['id'])
        assert pedido.status_pagamento == Pedido.StatusPagamento.PENDENTE
        assert pedido.status == Pedido.Status.PENDENTE
        assert pedido.mercadopago_order_id == 'ORD01TESTPIX'

        payload = post.call_args.kwargs['json']
        pagamento = payload['transactions']['payments'][0]
        assert pagamento['payment_method'] == {
            'id': 'pix',
            'type': 'bank_transfer',
        }
        assert pagamento['expiration_time'] == 'PT45M'
        assert payload['payer']['email'] == 'test_user_br@testuser.com'
        assert payload['payer']['first_name'] == 'APRO'

    @patch('pedidos.services.pagamentos.requests.post')
    def test_order_falhou_devolve_estoque(self, post):
        estoque = self.coxinha.estoque
        resposta_mp = Mock(status_code=201)
        resposta_mp.json.return_value = {
            'id': 'ORD01FAILED',
            'status': 'failed',
            'status_detail': 'failed',
            'transactions': {
                'payments': [
                    {
                        'id': 'PAY01FAILED',
                        'status': 'failed',
                        'status_detail': 'high_risk',
                        'payment_method': {
                            'id': 'visa',
                            'type': 'credit_card',
                        },
                    }
                ]
            },
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

    @patch('pedidos.services.pagamentos.requests.post')
    def test_card_3ds_retorna_challenge_url(self, post):
        resposta_mp = Mock(status_code=201)
        resposta_mp.json.return_value = {
            'id': 'ORD013DS',
            'status': 'action_required',
            'status_detail': 'pending_challenge',
            'transactions': {
                'payments': [
                    {
                        'id': 'PAY013DS',
                        'status': 'action_required',
                        'status_detail': 'pending_challenge',
                        'payment_method': {
                            'id': 'master',
                            'type': 'credit_card',
                            'transaction_security': {
                                'url': 'https://www.mercadopago.com/auth/card/challenge',
                            },
                        },
                    }
                ]
            },
        }
        post.return_value = resposta_mp

        resposta = self.client.post(
            '/api/pedidos/checkout_mercado_pago/',
            {
                'checkout_id': str(uuid4()),
                'itens_criacao': self.itens(),
                'payment_type': 'credit_card',
                'form_data': {
                    'payment_method_id': 'master',
                    'token': 'token-3ds',
                    'installments': 1,
                    'payer': {'email': 'aluno@teste.com'},
                },
            },
            format='json',
        )

        assert resposta.status_code == status.HTTP_201_CREATED
        assert resposta.data['pagamento']['status_pagamento'] == 'processando'
        assert resposta.data['pagamento']['mercadopago_challenge_url'].startswith(
            'https://www.mercadopago.com/'
        )

    @patch('pedidos.services.pagamentos.requests.get')
    def test_webhook_order_sincroniza_pagamento(self, get):
        pedido = Pedido.objects.create(
            usuario=self.aluno,
            forma_pagamento=Pedido.FormaPagamento.PIX,
            status_pagamento=Pedido.StatusPagamento.PENDENTE,
            mercadopago_order_id='ORD01WEBHOOK',
        )

        resposta_mp = Mock(status_code=200)
        resposta_mp.json.return_value = {
            'id': 'ORD01WEBHOOK',
            'external_reference': str(pedido.id),
            'status': 'processed',
            'status_detail': 'accredited',
            'transactions': {
                'payments': [
                    {
                        'id': 'PAY01WEBHOOK',
                        'status': 'processed',
                        'status_detail': 'accredited',
                        'payment_method': {'id': 'pix', 'type': 'bank_transfer'},
                    }
                ]
            },
        }
        get.return_value = resposta_mp

        data_id = 'ORD01WEBHOOK'
        request_id = 'request-123'
        ts = '1742505638683'
        manifest = f'id:{data_id.lower()};request-id:{request_id};ts:{ts};'
        assinatura = hmac.new(
            b'segredo-teste',
            manifest.encode(),
            hashlib.sha256,
        ).hexdigest()

        self.client.force_authenticate(user=None)
        resposta = self.client.post(
            f'/api/pedidos/mercado_pago_webhook/?data.id={data_id}&type=order',
            {},
            format='json',
            HTTP_X_SIGNATURE=f'ts={ts},v1={assinatura}',
            HTTP_X_REQUEST_ID=request_id,
        )

        assert resposta.status_code == status.HTTP_200_OK
        pedido.refresh_from_db()
        assert pedido.status_pagamento == Pedido.StatusPagamento.APROVADO
        assert pedido.status == Pedido.Status.CONFIRMADO
        assert pedido.mercadopago_payment_id == 'PAY01WEBHOOK'
