"""
Model de Produto (itens vendidos na cantina).
"""

from django.db import models
from django.utils import timezone


class Produto(models.Model):
    """Produto disponível para venda/reserva na cantina (RF02, RF09)."""

    class Categoria(models.TextChoices):
        SALGADO = 'salgado', 'Salgado'
        DOCE = 'doce', 'Doce'
        BEBIDA = 'bebida', 'Bebida'
        OUTRO = 'outro', 'Outro'

    nome = models.CharField(max_length=255, verbose_name='nome')
    descricao = models.TextField(blank=True, verbose_name='descrição')
    preco = models.DecimalField(max_digits=7, decimal_places=2, verbose_name='preço')
    estoque = models.PositiveIntegerField(default=0, verbose_name='estoque')
    categoria = models.CharField(
        max_length=20, choices=Categoria.choices, default=Categoria.OUTRO, verbose_name='categoria'
    )
    ativo = models.BooleanField(default=True, verbose_name='ativo')

    class Meta:
        """Meta options for the model."""

        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def promocao_ativa(self):
        """Retorna a promoção vigente do produto hoje, se houver (RN05)."""
        hoje = timezone.localdate()
        return self.promocoes.filter(data_inicio__lte=hoje, data_fim__gte=hoje).order_by('-data_inicio').first()

    @property
    def preco_atual(self):
        """Preço do produto considerando promoção ativa, se houver."""
        promocao = self.promocao_ativa
        return promocao.preco_promocional if promocao else self.preco
