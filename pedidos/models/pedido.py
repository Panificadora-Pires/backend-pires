"""
Models de Pedido e ItemPedido.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class Pedido(models.Model):
    """
    Pedido realizado por um aluno.

    RF04 — criação de pedido.
    RF07 — gerenciamento de status.
    RF10 — acompanhamento do pedido.
    """

    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        CONFIRMADO = 'confirmado', 'Confirmado'
        PRONTO = 'pronto', 'Pronto'
        RETIRADO = 'retirado', 'Retirado'
        CANCELADO = 'cancelado', 'Cancelado'

    TRANSICOES_PERMITIDAS = {
        Status.PENDENTE: {
            Status.CONFIRMADO,
            Status.CANCELADO,
        },
        Status.CONFIRMADO: {
            Status.PRONTO,
            Status.CANCELADO,
        },
        Status.PRONTO: {
            Status.RETIRADO,
            Status.CANCELADO,
        },
        Status.RETIRADO: set(),
        Status.CANCELADO: set(),
    }

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pedidos',
        verbose_name='usuário',
    )

    data = models.DateTimeField(
        auto_now_add=True,
        verbose_name='data do pedido',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
        verbose_name='status',
    )

    status_atualizado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='status atualizado em',
        help_text=(
            'Marca desde quando o pedido está no status atual. '
            'Usado no cancelamento automático e nos relatórios.'
        ),
    )

    codigo_retirada = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name='código de retirada',
    )

    class Meta:
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-data']

    def __str__(self):
        return (
            f'Pedido #{self.pk} — '
            f'{self.usuario} '
            f'({self.get_status_display()})'
        )

    @property
    def total(self):
        """Calcula o valor total do pedido."""

        return sum(
            (
                item.subtotal
                for item in self.itens.all()
            ),
            Decimal('0.00'),
        )

    def pode_transicionar_para(self, novo_status):
        """Verifica se uma transição de status é válida."""

        status_permitidos = self.TRANSICOES_PERMITIDAS.get(
            self.status,
            set(),
        )

        return novo_status in status_permitidos


class ItemPedido(models.Model):
    """Produto e quantidade pertencentes a um pedido."""

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name='itens',
        verbose_name='pedido',
    )

    produto = models.ForeignKey(
        'catalogo.Produto',
        on_delete=models.PROTECT,
        related_name='itens_pedido',
        verbose_name='produto',
    )

    quantidade = models.PositiveIntegerField(
        verbose_name='quantidade',
    )

    preco_unitario = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        verbose_name='preço unitário no momento do pedido',
    )

    class Meta:
        verbose_name = 'Item do pedido'
        verbose_name_plural = 'Itens do pedido'

    def __str__(self):
        return (
            f'{self.quantidade}x '
            f'{self.produto.nome}'
        )

    @property
    def subtotal(self):
        return self.preco_unitario * self.quantidade
