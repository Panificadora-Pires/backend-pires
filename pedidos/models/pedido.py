"""
Models de Pedido e ItemPedido.
"""

import uuid

from django.conf import settings
from django.db import models


class Pedido(models.Model):
    """Pedido (reserva antecipada) feito por um aluno (RF04, RF07, RF10)."""

    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        CONFIRMADO = 'confirmado', 'Confirmado'
        PRONTO = 'pronto', 'Pronto'
        RETIRADO = 'retirado', 'Retirado'
        CANCELADO = 'cancelado', 'Cancelado'

    # RN04 — transições de status permitidas
    TRANSICOES_PERMITIDAS = {
        Status.PENDENTE: {Status.CONFIRMADO, Status.CANCELADO},
        Status.CONFIRMADO: {Status.PRONTO, Status.CANCELADO},
        Status.PRONTO: {Status.RETIRADO, Status.CANCELADO},
        Status.RETIRADO: set(),
        Status.CANCELADO: set(),
    }

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pedidos', verbose_name='usuário'
    )
    data = models.DateTimeField(auto_now_add=True, verbose_name='data do pedido')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE, verbose_name='status'
    )
    status_atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='status atualizado em',
        help_text='Marca desde quando o pedido está no status atual (usado pela RN06).',
    )
    # Token único usado para gerar o QR Code de retirada. Não é o ID sequencial
    # do pedido de propósito: um UUID não é adivinhável, então ninguém
    # consegue "retirar" o pedido de outra pessoa só testando IDs em sequência.
    codigo_retirada = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, verbose_name='código de retirada'
    )
    # Usado pela RN06 (cancelamento automático) e pelo relatório de vendas
    # (RF11): marca desde quando o pedido está no status atual. Atualizado
    # manualmente sempre que o status muda (ver PedidoStatusUpdateSerializer
    # e RetiradaPorQRCodeSerializer) — decidi não usar auto_now porque isso
    # atualizaria o campo em QUALQUER save(), não só quando o status muda.
    status_atualizado_em = models.DateTimeField(auto_now_add=True, verbose_name='status atualizado em')

    class Meta:
        """Meta options for the model."""

        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-data']

    def __str__(self):
        return f'Pedido #{self.pk} — {self.usuario} ({self.get_status_display()})'

    @property
    def total(self):
        """Soma os subtotais dos itens do pedido."""
        return sum((item.subtotal for item in self.itens.all()), start=0)

    def pode_transicionar_para(self, novo_status):
        """Verifica se a mudança de status é permitida pela RN04."""
        return novo_status in self.TRANSICOES_PERMITIDAS.get(self.status, set())


class ItemPedido(models.Model):
    """Item (produto + quantidade) dentro de um pedido."""

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='itens', verbose_name='pedido')
    # Referência ao Produto via string ('catalogo.Produto') porque Produto
    # mora em outro app — evita import circular entre catalogo e pedidos.
    produto = models.ForeignKey(
        'catalogo.Produto', on_delete=models.PROTECT, related_name='itens_pedido', verbose_name='produto'
    )
    quantidade = models.PositiveIntegerField(verbose_name='quantidade')
    # Preço "congelado" no momento do pedido, para não ser afetado por mudanças
    # futuras no preço do produto ou pelo fim de uma promoção.
    preco_unitario = models.DecimalField(
        max_digits=7, decimal_places=2, verbose_name='preço unitário no momento do pedido'
    )

    class Meta:
        """Meta options for the model."""

        verbose_name = 'Item do pedido'
        verbose_name_plural = 'Itens do pedido'

    def __str__(self):
        return f'{self.quantidade}x {self.produto.nome}'

    @property
    def subtotal(self):
        return self.preco_unitario * self.quantidade
