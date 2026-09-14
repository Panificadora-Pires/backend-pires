"""
RN06 e pagamentos online:
- cancela pedidos prontos não retirados no prazo;
- cancela orders online que ficaram pendentes além do limite;
- devolve estoque exatamente uma vez.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
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


class Command(BaseCommand):
    help = 'Cancela pedidos prontos vencidos e checkouts online não pagos.'

    def handle(self, *args, **options):
        agora = timezone.now()
        limite_retirada = agora - timedelta(
            minutes=settings.PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS,
        )

        prontos_expirados = Pedido.objects.filter(
            status=Pedido.Status.PRONTO,
            status_atualizado_em__lte=limite_retirada,
        )

        cancelados_retirada = 0
        ignorados_por_falha = 0
        for pedido in prontos_expirados:
            if pedido.forma_pagamento in {
                Pedido.FormaPagamento.PIX,
                Pedido.FormaPagamento.CARTAO,
            }:
                try:
                    pedido = preparar_cancelamento_financeiro(pedido)
                except MercadoPagoError:
                    ignorados_por_falha += 1
                    continue

            pedido.status = Pedido.Status.CANCELADO
            pedido.status_atualizado_em = agora
            pedido.save(
                update_fields=['status', 'status_atualizado_em', 'status_pagamento']
            )
            devolver_estoque_pedido(pedido)
            cancelados_retirada += 1

        online_expirados = Pedido.objects.filter(
            forma_pagamento__in=[
                Pedido.FormaPagamento.PIX,
                Pedido.FormaPagamento.CARTAO,
            ],
            pagamento_expira_em__isnull=False,
            pagamento_expira_em__lte=agora,
        ).exclude(
            status_pagamento=Pedido.StatusPagamento.APROVADO,
        ).exclude(
            status=Pedido.Status.CANCELADO,
        )

        cancelados_pagamento = 0

        for pedido in online_expirados:
            # Uma order sem ID após timeout é um estado financeiro incerto. Não
            # liberamos estoque até que a tentativa seja conciliada.
            if not pedido.mercadopago_order_id:
                ignorados_por_falha += 1
                continue

            try:
                remoto = consultar_order_mercado_pago(
                    pedido.mercadopago_order_id,
                )
                pedido = aplicar_dados_order(pedido, remoto)
            except MercadoPagoError:
                ignorados_por_falha += 1
                continue

            if pedido.status_pagamento == Pedido.StatusPagamento.APROVADO:
                continue

            if pedido.status == Pedido.Status.CANCELADO:
                cancelados_pagamento += 1
                continue

            try:
                remoto = cancelar_order_mercado_pago(pedido)
                pedido = aplicar_dados_order(pedido, remoto)
            except MercadoPagoError:
                ignorados_por_falha += 1
                continue

            if pedido.status != Pedido.Status.CANCELADO:
                pedido.status = Pedido.Status.CANCELADO
                pedido.status_pagamento = Pedido.StatusPagamento.CANCELADO
                pedido.status_atualizado_em = agora
                pedido.pagamento_expira_em = None
                pedido.save(
                    update_fields=[
                        'status',
                        'status_pagamento',
                        'status_atualizado_em',
                        'pagamento_expira_em',
                    ]
                )
                devolver_estoque_pedido(pedido)

            cancelados_pagamento += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'{cancelados_retirada} pedido(s) pronto(s) cancelado(s) por atraso na retirada.'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'{cancelados_pagamento} checkout(s) online cancelado(s) por falta de pagamento.'
            )
        )
        if ignorados_por_falha:
            self.stdout.write(
                self.style.WARNING(
                    f'{ignorados_por_falha} pagamento(s) não foram cancelados porque a order não pôde ser conciliada.'
                )
            )
