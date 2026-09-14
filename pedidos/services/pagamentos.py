"""Integração com Mercado Pago Checkout Transparente via Orders API."""

import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from pedidos.models import Pedido
from pedidos.services.pedido import devolver_estoque_pedido


class MercadoPagoError(Exception):
    """Erro controlado ao conversar com a API do Mercado Pago."""

    def __init__(self, message, *, status_code=None, data=None, estado_incerto=False):
        super().__init__(message)
        self.status_code = status_code
        self.data = data or {}
        self.estado_incerto = estado_incerto


def _access_token():
    token = settings.MERCADO_PAGO_ACCESS_TOKEN
    if not token:
        raise MercadoPagoError(
            'Mercado Pago ainda não foi configurado no servidor.',
            status_code=503,
        )
    return token


def _url(path):
    return f'{settings.MERCADO_PAGO_API_BASE_URL.rstrip("/")}{path}'


def _headers(*, idempotency_key=None):
    headers = {
        'Authorization': f'Bearer {_access_token()}',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if idempotency_key:
        headers['X-Idempotency-Key'] = str(idempotency_key)
    return headers


def _json_response(response):
    try:
        data = response.json()
    except ValueError:
        data = {}

    if response.status_code >= 400:
        erros = data.get('errors') if isinstance(data, dict) else None
        primeiro_erro = erros[0] if isinstance(erros, list) and erros else {}
        detalhe = (
            data.get('message')
            or data.get('error')
            or data.get('detail')
            or primeiro_erro.get('message')
            or primeiro_erro.get('code')
            or 'O Mercado Pago recusou a solicitação.'
        ) if isinstance(data, dict) else 'O Mercado Pago recusou a solicitação.'
        raise MercadoPagoError(
            str(detalhe),
            status_code=response.status_code,
            data=data if isinstance(data, dict) else {},
        )

    return data


def _valor(valor):
    return f'{Decimal(valor):.2f}'


def _payer(form_data, pedido, *, eh_pix=False):
    payer_recebido = form_data.get('payer') or {}

    # As credenciais sandbox da Orders API exigem dados de pagador próprios
    # para os cenários oficiais de teste. Em produção usamos os dados reais.
    if settings.MERCADO_PAGO_SANDBOX:
        payer = {
            'email': (
                'test_user_br@testuser.com'
                if eh_pix
                else 'test@testuser.com'
            ),
        }
        if eh_pix:
            payer['first_name'] = 'APRO'
    else:
        payer = {
            'email': payer_recebido.get('email') or pedido.usuario.email,
        }

    identificacao = payer_recebido.get('identification') or {}
    if identificacao.get('type') and identificacao.get('number'):
        payer['identification'] = {
            'type': identificacao['type'],
            'number': identificacao['number'],
        }

    return payer


def _primeiro_pagamento(order_data):
    pagamentos = ((order_data.get('transactions') or {}).get('payments') or [])
    return pagamentos[0] if pagamentos else {}


def _payment_method(order_data):
    return _primeiro_pagamento(order_data).get('payment_method') or {}


def forma_pagamento_por_dados(payment_type, dados):
    if str(dados.get('payment_method_id') or '') == 'pix':
        return Pedido.FormaPagamento.PIX
    if payment_type in {'credit_card', 'debit_card', 'prepaid_card'}:
        return Pedido.FormaPagamento.CARTAO
    return None


def _forma_pagamento_order(order_data):
    metodo = _payment_method(order_data)
    if metodo.get('id') == 'pix' or metodo.get('type') == 'bank_transfer':
        return Pedido.FormaPagamento.PIX
    if metodo.get('type') in {'credit_card', 'debit_card', 'prepaid_card'}:
        return Pedido.FormaPagamento.CARTAO
    return None


def criar_order_mercado_pago(*, pedido, payment_type, form_data):
    """Cria e processa uma order via Checkout Transparente / Orders API."""

    payment_method_id = str(form_data.get('payment_method_id') or '').strip()
    payment_type = str(payment_type or '').strip()

    if not payment_method_id:
        raise MercadoPagoError('Meio de pagamento não informado.', status_code=400)

    eh_pix = payment_method_id == 'pix'
    tipos_cartao = {'credit_card', 'debit_card', 'prepaid_card'}

    if not eh_pix and payment_type not in tipos_cartao:
        raise MercadoPagoError(
            'Este checkout aceita somente Pix ou cartão.',
            status_code=400,
        )

    if not eh_pix and not form_data.get('token'):
        raise MercadoPagoError('Token do cartão não informado.', status_code=400)

    total = _valor(pedido.total)
    metodo = {
        'id': payment_method_id,
        'type': 'bank_transfer' if eh_pix else payment_type,
    }

    if not eh_pix:
        metodo['token'] = form_data['token']
        metodo['installments'] = int(form_data.get('installments') or 1)

    pagamento = {
        'amount': total,
        'payment_method': metodo,
    }

    # A Orders API aceita expiração de Pix a partir de 30 minutos. Usamos no
    # mínimo 45 min para também comportar fluxos 3DS, que podem levar até 40 min.
    if eh_pix:
        minutos = max(int(settings.PAGAMENTO_TEMPO_LIMITE_MINUTOS), 45)
        pagamento['expiration_time'] = f'PT{minutos}M'

    payload = {
        'type': 'online',
        'processing_mode': 'automatic',
        'total_amount': total,
        'external_reference': str(pedido.id),
        'payer': _payer(form_data, pedido, eh_pix=eh_pix),
        'transactions': {
            'payments': [pagamento],
        },
    }

    # 3DS é acionado pelo Mercado Pago quando houver risco, sem forçar desafio
    # em todas as compras. O challenge, quando necessário, é tratado no frontend.
    if not eh_pix:
        payload['config'] = {
            'online': {
                'transaction_security': {
                    'validation': 'on_fraud_risk',
                    'liability_shift': 'required',
                }
            }
        }

    try:
        response = requests.post(
            _url('/v1/orders'),
            json=payload,
            headers=_headers(idempotency_key=pedido.checkout_id),
            timeout=settings.MERCADO_PAGO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        # Em timeout não sabemos se a order foi criada. O usuário pode repetir
        # o mesmo checkout e a mesma X-Idempotency-Key sem duplicar a cobrança.
        raise MercadoPagoError(
            'Não foi possível confirmar a resposta do Mercado Pago. Tente novamente.',
            status_code=503,
            estado_incerto=True,
        ) from exc

    return _json_response(response)


def consultar_order_mercado_pago(order_id):
    try:
        response = requests.get(
            _url(f'/v1/orders/{order_id}'),
            headers=_headers(),
            timeout=settings.MERCADO_PAGO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise MercadoPagoError(
            'Não foi possível consultar a order no Mercado Pago.',
            status_code=503,
            estado_incerto=True,
        ) from exc

    return _json_response(response)


def cancelar_order_mercado_pago(pedido):
    """Cancela uma order ainda não processada."""

    if not pedido.mercadopago_order_id:
        raise MercadoPagoError(
            'A order do Mercado Pago ainda não foi conciliada.',
            status_code=409,
            estado_incerto=True,
        )

    try:
        response = requests.post(
            _url(f'/v1/orders/{pedido.mercadopago_order_id}/cancel'),
            json={},
            headers=_headers(idempotency_key=f'{pedido.checkout_id}-cancel'),
            timeout=settings.MERCADO_PAGO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise MercadoPagoError(
            'Não foi possível cancelar a order no Mercado Pago.',
            status_code=503,
            estado_incerto=True,
        ) from exc

    return _json_response(response)


def reembolsar_order_mercado_pago(pedido):
    """Executa reembolso total de uma order já processada."""

    if not pedido.mercadopago_order_id:
        raise MercadoPagoError(
            'O pedido não possui ID de order para reembolso.',
            status_code=400,
        )

    try:
        response = requests.post(
            _url(f'/v1/orders/{pedido.mercadopago_order_id}/refund'),
            json={},
            headers=_headers(idempotency_key=f'{pedido.checkout_id}-refund'),
            timeout=settings.MERCADO_PAGO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise MercadoPagoError(
            'Não foi possível reembolsar a order no Mercado Pago.',
            status_code=503,
            estado_incerto=True,
        ) from exc

    return _json_response(response)


def _status_interno(order_data):
    order_status = str(order_data.get('status') or '')
    order_detail = str(order_data.get('status_detail') or '')
    transacao = _primeiro_pagamento(order_data)
    tx_status = str(transacao.get('status') or '')
    tx_detail = str(transacao.get('status_detail') or '')

    if order_status == 'refunded' or tx_status == 'refunded':
        return Pedido.StatusPagamento.REEMBOLSADO

    if order_status == 'processed' or tx_status == 'processed':
        return Pedido.StatusPagamento.APROVADO

    if order_status == 'failed' or tx_status == 'failed':
        return Pedido.StatusPagamento.RECUSADO

    if order_status in {'canceled', 'expired', 'charged_back'} or tx_status in {
        'canceled',
        'expired',
        'charged_back',
    }:
        return Pedido.StatusPagamento.CANCELADO

    if order_status == 'action_required' or tx_status == 'action_required':
        detalhe = tx_detail or order_detail
        if detalhe in {'waiting_payment', 'waiting_transfer'}:
            return Pedido.StatusPagamento.PENDENTE
        return Pedido.StatusPagamento.PROCESSANDO

    if order_status in {'created', 'processing', 'in_review'} or tx_status in {
        'created',
        'processing',
        'in_review',
    }:
        return Pedido.StatusPagamento.PROCESSANDO

    return Pedido.StatusPagamento.ERRO


def _challenge_url(order_data):
    seguranca = _payment_method(order_data).get('transaction_security') or {}
    return str(seguranca.get('url') or '')


def _dados_pix(order_data):
    metodo = _payment_method(order_data)
    if metodo.get('id') != 'pix' and metodo.get('type') != 'bank_transfer':
        return {}
    return metodo


@transaction.atomic
def aplicar_dados_order(pedido, order_data, *, payment_type=None):
    """Concilia resposta/webhook da Orders API de forma idempotente."""

    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    status_interno = _status_interno(order_data)
    forma = _forma_pagamento_order(order_data) or forma_pagamento_por_dados(
        payment_type,
        _payment_method(order_data),
    )

    order_id = order_data.get('id')
    if order_id:
        pedido.mercadopago_order_id = str(order_id)

    transacao = _primeiro_pagamento(order_data)
    payment_id = transacao.get('id')
    if payment_id:
        pedido.mercadopago_payment_id = str(payment_id)

    pedido.mercadopago_status = str(order_data.get('status') or '')
    pedido.mercadopago_status_detail = str(order_data.get('status_detail') or '')
    pedido.status_pagamento = status_interno

    if forma:
        pedido.forma_pagamento = forma

    pix = _dados_pix(order_data)
    if pix.get('qr_code'):
        pedido.pix_qr_code = pix['qr_code']
    if pix.get('qr_code_base64'):
        pedido.pix_qr_code_base64 = pix['qr_code_base64']

    pedido.mercadopago_challenge_url = _challenge_url(order_data)

    campos = [
        'mercadopago_order_id',
        'mercadopago_payment_id',
        'mercadopago_status',
        'mercadopago_status_detail',
        'mercadopago_challenge_url',
        'status_pagamento',
        'forma_pagamento',
        'pix_qr_code',
        'pix_qr_code_base64',
    ]

    if status_interno in {
        Pedido.StatusPagamento.APROVADO,
        Pedido.StatusPagamento.RECUSADO,
        Pedido.StatusPagamento.CANCELADO,
        Pedido.StatusPagamento.REEMBOLSADO,
    }:
        pedido.pagamento_expira_em = None
        pedido.mercadopago_challenge_url = ''
        campos += ['pagamento_expira_em', 'mercadopago_challenge_url']

    if status_interno == Pedido.StatusPagamento.APROVADO:
        if pedido.status == Pedido.Status.PENDENTE:
            pedido.status = Pedido.Status.CONFIRMADO
            pedido.status_atualizado_em = timezone.now()
            campos += ['status', 'status_atualizado_em']

    if status_interno in {
        Pedido.StatusPagamento.RECUSADO,
        Pedido.StatusPagamento.CANCELADO,
        Pedido.StatusPagamento.REEMBOLSADO,
    }:
        if pedido.status not in {
            Pedido.Status.RETIRADO,
            Pedido.Status.CANCELADO,
        }:
            pedido.status = Pedido.Status.CANCELADO
            pedido.status_atualizado_em = timezone.now()
            campos += ['status', 'status_atualizado_em']

    pedido.save(update_fields=list(dict.fromkeys(campos)))

    if pedido.status == Pedido.Status.CANCELADO:
        devolver_estoque_pedido(pedido)

    return Pedido.objects.get(pk=pedido.pk)


def preparar_cancelamento_financeiro(pedido):
    """Concilia/cancela/reembolsa a order antes de cancelar o pedido local."""

    if pedido.forma_pagamento == Pedido.FormaPagamento.DINHEIRO:
        return pedido

    if pedido.forma_pagamento not in {
        Pedido.FormaPagamento.PIX,
        Pedido.FormaPagamento.CARTAO,
    }:
        return pedido

    if not pedido.mercadopago_order_id:
        raise MercadoPagoError(
            'A order do Mercado Pago ainda não foi conciliada. Tente novamente em instantes.',
            status_code=409,
            estado_incerto=True,
        )

    remoto = consultar_order_mercado_pago(pedido.mercadopago_order_id)
    pedido = aplicar_dados_order(pedido, remoto)

    if pedido.status_pagamento == Pedido.StatusPagamento.APROVADO:
        remoto = reembolsar_order_mercado_pago(pedido)
        pedido = aplicar_dados_order(pedido, remoto)
        if pedido.status_pagamento != Pedido.StatusPagamento.REEMBOLSADO:
            pedido.status_pagamento = Pedido.StatusPagamento.REEMBOLSADO
            pedido.save(update_fields=['status_pagamento'])
        return pedido

    if pedido.status_pagamento not in {
        Pedido.StatusPagamento.CANCELADO,
        Pedido.StatusPagamento.REEMBOLSADO,
        Pedido.StatusPagamento.RECUSADO,
    }:
        remoto = cancelar_order_mercado_pago(pedido)
        pedido = aplicar_dados_order(pedido, remoto)

    return pedido


def prazo_pagamento():
    # 45 minutos cobre o mínimo do Pix (30 min) e o timeout máximo do challenge
    # 3DS (40 min), mesmo que um .env antigo ainda esteja com valor menor.
    minutos = max(int(settings.PAGAMENTO_TEMPO_LIMITE_MINUTOS), 45)
    return timezone.now() + timedelta(minutes=minutos)


def validar_assinatura_webhook(*, x_signature, x_request_id, data_id):
    """Valida x-signature conforme o manifesto HMAC do Mercado Pago."""

    secret = settings.MERCADO_PAGO_WEBHOOK_SECRET
    if not secret or not x_signature:
        return False

    partes = {}
    for parte in x_signature.split(','):
        chave, separador, valor = parte.partition('=')
        if separador:
            partes[chave.strip()] = valor.strip()

    timestamp = partes.get('ts')
    assinatura = partes.get('v1')
    if not timestamp or not assinatura:
        return False

    data_id = str(data_id or '')
    if data_id.isalnum():
        data_id = data_id.lower()

    manifest_parts = []
    if data_id:
        manifest_parts.append(f'id:{data_id};')
    if x_request_id:
        manifest_parts.append(f'request-id:{x_request_id};')
    manifest_parts.append(f'ts:{timestamp};')

    esperado = hmac.new(
        secret.encode(),
        ''.join(manifest_parts).encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(esperado, assinatura)
