"""Expiração automática de pedidos (retirada vencida, pagamento online não concluído e preparo parado).

Usada pelo comando ``cancelar_pedidos_expirados`` e pelo endpoint de manutenção, de modo que o mesmo
código roda tanto por cron do servidor quanto por um agendador externo (ex.: GitHub Actions).
"""

import logging
from dataclasses import asdict, dataclass
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from pedidos.models import Pedido
from pedidos.services.pagamentos import (
    MercadoPagoError,
    aplicar_dados_order,
    cancelar_order_mercado_pago,
    consultar_order_mercado_pago,
    preparar_cancelamento_financeiro,
)
from pedidos.services.pedido import devolver_estoque_pedido

logger = logging.getLogger(__name__)

PAGAMENTOS_ONLINE = (
    Pedido.FormaPagamento.PIX,
    Pedido.FormaPagamento.CARTAO,
)


@dataclass
class ResultadoExpiracao:
    cancelados_retirada: int = 0
    cancelados_pagamento: int = 0
    cancelados_preparo: int = 0
    ignorados_por_falha: int = 0

    def como_dict(self):
        return asdict(self)


def _cancelar_pronto_expirado(pedido, agora, resultado):
    if pedido.forma_pagamento in PAGAMENTOS_ONLINE:
        try:
            pedido = preparar_cancelamento_financeiro(pedido)
        except MercadoPagoError:
            resultado.ignorados_por_falha += 1
            logger.warning('Expiração: pedido #%s não pôde ser conciliado no Mercado Pago.', pedido.pk)
            return False

    pedido.status = Pedido.Status.CANCELADO
    pedido.status_atualizado_em = agora
    pedido.save(update_fields=['status', 'status_atualizado_em', 'status_pagamento'])
    devolver_estoque_pedido(pedido)
    return True


def _cancelar_pagamento_expirado(pedido, agora, resultado):
    # Uma order sem ID após timeout é um estado financeiro incerto. Não liberamos
    # estoque até que a tentativa seja conciliada.
    if not pedido.mercadopago_order_id:
        resultado.ignorados_por_falha += 1
        logger.warning('Expiração: pedido #%s sem order do Mercado Pago; mantido para conciliação.', pedido.pk)
        return False

    try:
        remoto = consultar_order_mercado_pago(pedido.mercadopago_order_id)
        pedido = aplicar_dados_order(pedido, remoto)
    except MercadoPagoError:
        resultado.ignorados_por_falha += 1
        return False

    if pedido.status_pagamento == Pedido.StatusPagamento.APROVADO:
        return False

    if pedido.status == Pedido.Status.CANCELADO:
        return True

    try:
        remoto = cancelar_order_mercado_pago(pedido)
        pedido = aplicar_dados_order(pedido, remoto)
    except MercadoPagoError:
        resultado.ignorados_por_falha += 1
        return False

    if pedido.status != Pedido.Status.CANCELADO:
        pedido.status = Pedido.Status.CANCELADO
        pedido.status_pagamento = Pedido.StatusPagamento.CANCELADO
        pedido.status_atualizado_em = agora
        pedido.pagamento_expira_em = None
        pedido.save(update_fields=['status', 'status_pagamento', 'status_atualizado_em', 'pagamento_expira_em'])
        devolver_estoque_pedido(pedido)

    return True


def _cancelar_preparo_parado(pedido, agora, resultado):
    """Cancela (e reembolsa, se pago online) pedidos confirmados que ninguém preparou."""

    try:
        pedido = preparar_cancelamento_financeiro(pedido)
    except MercadoPagoError:
        resultado.ignorados_por_falha += 1
        logger.warning('Expiração: reembolso do pedido #%s falhou; mantido para nova tentativa.', pedido.pk)
        return False

    pedido.status = Pedido.Status.CANCELADO
    pedido.status_atualizado_em = agora
    pedido.save(update_fields=['status', 'status_atualizado_em', 'status_pagamento'])
    devolver_estoque_pedido(pedido)
    return True


def expirar_pedidos(agora=None):
    """Executa todas as regras de expiração e devolve um resumo numérico."""

    agora = agora or timezone.now()
    resultado = ResultadoExpiracao()

    # 1) Pedidos prontos que não foram retirados no prazo (RN06).
    limite_retirada = agora - timedelta(minutes=settings.PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS)
    prontos_expirados = Pedido.objects.filter(
        status=Pedido.Status.PRONTO,
        status_atualizado_em__lte=limite_retirada,
    )
    for pedido in prontos_expirados:
        if _cancelar_pronto_expirado(pedido, agora, resultado):
            resultado.cancelados_retirada += 1

    # 2) Checkouts online sem pagamento concluído. Pedidos antigos criados antes de existir
    #    `pagamento_expira_em` usam a data de criação como referência.
    limite_pagamento = agora - timedelta(minutes=max(int(settings.PAGAMENTO_TEMPO_LIMITE_MINUTOS), 45))
    online_expirados = (
        Pedido.objects.filter(forma_pagamento__in=PAGAMENTOS_ONLINE)
        .filter(
            Q(pagamento_expira_em__lte=agora)
            | Q(pagamento_expira_em__isnull=True, data__lte=limite_pagamento)
        )
        .exclude(status_pagamento__in=[
            Pedido.StatusPagamento.APROVADO,
            Pedido.StatusPagamento.REEMBOLSADO,
            Pedido.StatusPagamento.RECUSADO,
            Pedido.StatusPagamento.CANCELADO,
        ])
        .exclude(status__in=[Pedido.Status.CANCELADO, Pedido.Status.RETIRADO])
    )
    for pedido in online_expirados:
        if _cancelar_pagamento_expirado(pedido, agora, resultado):
            resultado.cancelados_pagamento += 1

    # 3) Pedidos confirmados que ninguém preparou. Desligado por padrão (0), pois cancela e reembolsa.
    horas_preparo = settings.PEDIDO_TEMPO_LIMITE_PREPARO_HORAS
    if horas_preparo > 0:
        limite_preparo = agora - timedelta(hours=horas_preparo)
        parados = Pedido.objects.filter(
            status=Pedido.Status.CONFIRMADO,
            status_atualizado_em__lte=limite_preparo,
        )
        for pedido in parados:
            if _cancelar_preparo_parado(pedido, agora, resultado):
                resultado.cancelados_preparo += 1

    logger.info('Expiração de pedidos concluída: %s', resultado.como_dict())
    return resultado
