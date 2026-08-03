"""
RN06 — cancela automaticamente pedidos "prontos" que passaram do tempo
limite de retirada, devolvendo os itens ao estoque.

Uso:
    pdm run python manage.py cancelar_pedidos_expirados

Pensado para ser chamado periodicamente por um Cron Job em produção (ver
issue de deploy/infra) — este comando não agenda nada sozinho, só executa
uma vez quando chamado.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from pedidos.models import Pedido


class Command(BaseCommand):
    help = 'Cancela pedidos "prontos" não retirados dentro do tempo limite (RN06) e devolve o estoque.'

    def handle(self, *args, **options):
        limite_minutos = settings.PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS
        limite = timezone.now() - timedelta(minutes=limite_minutos)

        pedidos_expirados = Pedido.objects.filter(
            status=Pedido.Status.PRONTO,
            status_atualizado_em__lte=limite,
        )

        total_cancelados = 0
        for pedido in pedidos_expirados:
            with transaction.atomic():
                for item in pedido.itens.select_related('produto'):
                    produto = item.produto
                    produto.estoque += item.quantidade
                    produto.save(update_fields=['estoque'])

                pedido.status = Pedido.Status.CANCELADO
                pedido.status_atualizado_em = timezone.now()
                pedido.save(update_fields=['status', 'status_atualizado_em'])
                total_cancelados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'{total_cancelados} pedido(s) cancelado(s) automaticamente '
                f'(prontos há mais de {limite_minutos} minuto(s) sem retirada).'
            )
        )
