"""
Model de Promoção, vinculada a um Produto.
"""

from django.core.exceptions import ValidationError
from django.db import models

from .produto import Produto


class Promocao(models.Model):
    """Promoção com preço especial para um produto, em um período (RF03, RN05)."""

    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name='promocoes', verbose_name='produto'
    )
    preco_promocional = models.DecimalField(max_digits=7, decimal_places=2, verbose_name='preço promocional')
    data_inicio = models.DateField(verbose_name='data de início')
    data_fim = models.DateField(verbose_name='data de fim')

    class Meta:
        """Meta options for the model."""

        verbose_name = 'Promoção'
        verbose_name_plural = 'Promoções'
        ordering = ['-data_inicio']

    def __str__(self):
        return f'{self.produto.nome} — R$ {self.preco_promocional}'

    def clean(self):
        """Validação de consistência entre datas e preço (usada pelo admin e pelo serializer)."""
        if self.data_fim and self.data_inicio and self.data_fim < self.data_inicio:
            raise ValidationError('A data de fim não pode ser anterior à data de início.')
        if self.produto_id and self.preco_promocional is not None and self.preco_promocional >= self.produto.preco:
            raise ValidationError('O preço promocional deve ser menor que o preço original do produto.')
