"""Integração de pagamentos online com Mercado Pago Checkout Bricks."""

import hashlib
import hmac
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from pedidos.models import Pedido
from pedidos.services.pedido import devolver_estoque_pedido

logger = logging.getLogger(__name__)


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
        detalhe = (
            data.get('message')
            or data.get('error')
            or data.get('detail')
            or 'O Mercado Pago recusou a solicitação.'
        )
        raise MercadoPagoError(
            str(detalhe),
            status_code=response.status_code,
            data=data,
        )

    return data


def _payer(form_data, pedido):
    payer_recebido = form_data.get('payer') or {}
    payer = {
        'email': payer_recebido.get('email') or pedido.usuario.email,
    }

    identificacao = payer_recebido.get('identification') or {}
    if identificacao.get('type') and identificacao.get('number'):
        payer['identification'] = {
            'type': identificacao['type'],
            'number': identificacao['number'],
        }

    if payer_recebido.get('first_name'):
        payer['first_name'] = payer_recebido['first_name']
    if payer_recebido.get('last_name'):
        payer['last_name'] = payer_recebido['last_name']

    return payer


def criar_pagamento_mercado_pago(*, pedido, payment_type, form_data):
    """Cria um pagamento real usando o token/dados produzidos pelo Payment Brick."""

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

    payload = {
        'transaction_amount': float(pedido.total),
        'description': f'Pires Panificadora - Pedido #{pedido.id}',
        'external_reference': str(pedido.id),
        'payment_method_id': payment_method_id,
        'payer': _payer(form_data, pedido),
        'metadata': {
            'pedido_id': pedido.id,
            'checkout_id': str(pedido.checkout_id),
        },
    }

    if settings.MERCADO_PAGO_WEBHOOK_URL:
        payload['notification_url'] = settings.MERCADO_PAGO_WEBHOOK_URL

    if not eh_pix:
        payload['token'] = form_data['token']
        payload['installments'] = int(form_data.get('installments') or 1)
        if form_data.get('issuer_id'):
            payload['issuer_id'] = form_data['issuer_id']

    try:
        response = requests.post(
            _url('/v1/payments'),
            json=payload,
            headers=_headers(idempotency_key=pedido.checkout_id),
            timeout=settings.MERCADO_PAGO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        # Em timeout não sabemos se o provedor processou a requisição. O pedido
        # fica reservado e pode ser retentado com a MESMA chave idempotente.
        raise MercadoPagoError(
            'Não foi possível confirmar a resposta do Mercado Pago. Tente novamente.',
            status_code=503,
            estado_incerto=True,
        ) from exc

    return _json_response(response)


def consultar_pagamento_mercado_pago(payment_id):
    try:
        response = requests.get(
            _url(f'/v1/payments/{payment_id}'),
            headers=_headers(),
            timeout=settings.MERCADO_PAGO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise MercadoPagoError(
            'Não foi possível consultar o pagamento no Mercado Pago.',
            status_code=503,
            estado_incerto=True,
        ) from exc

    return _json_response(response)


def buscar_pagamento_por_referencia(pedido):
    """Busca no provedor um pagamento perdido após timeout de rede."""

    try:
        response = requests.get(
            _url('/v1/payments/search'),
            params={
                'external_reference': str(pedido.id),
                'sort': 'date_created',
                'criteria': 'desc',
                'limit': 1,
            },
            headers=_headers(),
            timeout=settings.MERCADO_PAGO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise MercadoPagoError(
            'Não foi possível pesquisar o pagamento no Mercado Pago.',
            status_code=503,
            estado_incerto=True,
        ) from exc

    data = _json_response(response)
    resultados = data.get('results') or []
    return resultados[0] if resultados else None


def cancelar_pagamento_mercado_pago(pedido):
    """Cancela no provedor um pagamento ainda pendente/processando."""

    if not pedido.mercadopago_payment_id:
        return None

    try:
        response = requests.put(
            _url(f'/v1/payments/{pedido.mercadopago_payment_id}'),
            json={'status': 'cancelled'},
            headers=_headers(idempotency_key=f'{pedido.checkout_id}-cancel'),
            timeout=settings.MERCADO_PAGO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise MercadoPagoError(
            'Não foi possível cancelar o pagamento no Mercado Pago.',
            status_code=503,
            estado_incerto=True,
        ) from exc

    return _json_response(response)



def reembolsar_pagamento_mercado_pago(pedido):
    """Executa reembolso total de um pagamento já aprovado."""

    if not pedido.mercadopago_payment_id:
        raise MercadoPagoError(
            'O pedido não possui ID de pagamento para reembolso.',
            status_code=400,
        )

    try:
        response = requests.post(
            _url(f'/v1/payments/{pedido.mercadopago_payment_id}/refunds'),
            json={},
            headers=_headers(idempotency_key=f'{pedido.checkout_id}-refund'),
            timeout=settings.MERCADO_PAGO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise MercadoPagoError(
            'Não foi possível reembolsar o pagamento no Mercado Pago.',
            status_code=503,
            estado_incerto=True,
        ) from exc

    return _json_response(response)


def preparar_cancelamento_financeiro(pedido):
    """Concilia/cancela/reembolsa o provedor antes de cancelar o pedido local."""

    if pedido.forma_pagamento == Pedido.FormaPagamento.DINHEIRO:
        return pedido

    if pedido.forma_pagamento not in {
        Pedido.FormaPagamento.PIX,
        Pedido.FormaPagamento.CARTAO,
    }:
        return pedido

    if pedido.mercadopago_payment_id:
        remoto = consultar_pagamento_mercado_pago(pedido.mercadopago_payment_id)
    else:
        remoto = buscar_pagamento_por_referencia(pedido)

    if remoto:
        pedido = aplicar_dados_pagamento(pedido, remoto)

    if pedido.status_pagamento == Pedido.StatusPagamento.APROVADO:
        reembolsar_pagamento_mercado_pago(pedido)
        pedido.status_pagamento = Pedido.StatusPagamento.REEMBOLSADO
        pedido.save(update_fields=['status_pagamento'])
        return pedido

    if (
        pedido.mercadopago_payment_id
        and pedido.status_pagamento not in {
            Pedido.StatusPagamento.CANCELADO,
            Pedido.StatusPagamento.REEMBOLSADO,
            Pedido.StatusPagamento.RECUSADO,
        }
    ):
        remoto = cancelar_pagamento_mercado_pago(pedido)
        if remoto:
            pedido = aplicar_dados_pagamento(pedido, remoto)

    return pedido

def forma_pagamento_por_dados(payment_type, dados):
    if str(dados.get('payment_method_id') or '') == 'pix':
        return Pedido.FormaPagamento.PIX
    if payment_type in {'credit_card', 'debit_card', 'prepaid_card'}:
        return Pedido.FormaPagamento.CARTAO
    return None


def _status_interno(status_mp):
    if status_mp == 'approved':
        return Pedido.StatusPagamento.APROVADO
    if status_mp in {'in_process', 'authorized'}:
        return Pedido.StatusPagamento.PROCESSANDO
    if status_mp == 'pending':
        return Pedido.StatusPagamento.PENDENTE
    if status_mp == 'rejected':
        return Pedido.StatusPagamento.RECUSADO
    if status_mp == 'refunded':
        return Pedido.StatusPagamento.REEMBOLSADO
    if status_mp in {'cancelled', 'canceled', 'charged_back'}:
        return Pedido.StatusPagamento.CANCELADO
    return Pedido.StatusPagamento.ERRO


def _dados_pix(dados):
    return (
        (dados.get('point_of_interaction') or {})
        .get('transaction_data')
        or {}
    )


@transaction.atomic
def aplicar_dados_pagamento(pedido, dados, *, payment_type=None):
    """Concilia resposta/webhook do Mercado Pago de forma idempotente."""

    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    status_mp = str(dados.get('status') or '')
    status_interno = _status_interno(status_mp)
    forma = forma_pagamento_por_dados(payment_type, dados)

    payment_id = dados.get('id')
    if payment_id:
        pedido.mercadopago_payment_id = str(payment_id)

    pedido.mercadopago_status = status_mp
    pedido.mercadopago_status_detail = str(dados.get('status_detail') or '')
    pedido.status_pagamento = status_interno

    if forma:
        pedido.forma_pagamento = forma

    pix = _dados_pix(dados)
    if pix.get('qr_code'):
        pedido.pix_qr_code = pix['qr_code']
    if pix.get('qr_code_base64'):
        pedido.pix_qr_code_base64 = pix['qr_code_base64']

    campos = [
        'mercadopago_payment_id',
        'mercadopago_status',
        'mercadopago_status_detail',
        'status_pagamento',
        'forma_pagamento',
        'pix_qr_code',
        'pix_qr_code_base64',
    ]

    if status_interno == Pedido.StatusPagamento.APROVADO:
        pedido.pagamento_expira_em = None
        campos.append('pagamento_expira_em')

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


def prazo_pagamento():
    return timezone.now() + timedelta(
        minutes=settings.PAGAMENTO_TEMPO_LIMITE_MINUTOS,
    )


def validar_assinatura_webhook(*, x_signature, x_request_id, data_id):
    """Valida x-signature conforme o manifesto oficial do Mercado Pago."""

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
    if timestamp:
        manifest_parts.append(f'ts:{timestamp};')

    manifest = ''.join(manifest_parts)
    esperado = hmac.new(
        secret.encode(),
        manifest.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(esperado, assinatura)
