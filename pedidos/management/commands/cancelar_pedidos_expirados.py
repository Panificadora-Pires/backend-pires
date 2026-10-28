"""
RN06 e pagamentos online:
- cancela pedidos prontos não retirados no prazo;
- cancela orders online que ficaram pendentes além do limite;
- (opcional) cancela pedidos confirmados parados há muito tempo;
- devolve estoque exatamente uma vez.

A lógica fica em ``pedidos.services.expiracao`` para ser reutilizada pelo endpoint de manutenção.
"""

from django.core.management.base import BaseCommand

from pedidos.services.expiracao import expirar_pedidos


class Command(BaseCommand):
    help = 'Cancela pedidos prontos vencidos, checkouts online não pagos e (opcional) pedidos confirmados parados.'

    def handle(self, *args, **options):
        resultado = expirar_pedidos()

        self.stdout.write(
            self.style.SUCCESS(
                f'{resultado.cancelados_retirada} pedido(s) pronto(s) cancelado(s) por atraso na retirada.'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'{resultado.cancelados_pagamento} checkout(s) online cancelado(s) por falta de pagamento.'
            )
        )
        if resultado.cancelados_preparo:
            self.stdout.write(
                self.style.SUCCESS(
                    f'{resultado.cancelados_preparo} pedido(s) confirmado(s) cancelado(s) por falta de preparo.'
                )
            )
        if resultado.ignorados_por_falha:
            self.stdout.write(
                self.style.WARNING(
                    f'{resultado.ignorados_por_falha} pagamento(s) não foram cancelados '
                    'porque a order não pôde ser conciliada.'
                )
            )
