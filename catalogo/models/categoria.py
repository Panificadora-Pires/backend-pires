"""
Model de Categoria de produto.
"""

from django.db import models
from django.utils.text import slugify


class Categoria(models.Model):
    """Categoria de produto (ex: Salgados, Doces, Bebidas).

    Existir como model (em vez de choices fixas no código) permite à
    administração criar/editar/desativar categorias sem depender de um novo
    deploy do backend — importante para um sistema que pode ser vendido a
    uma padaria de verdade.
    """

    nome = models.CharField(max_length=100, unique=True, verbose_name='nome')
    slug = models.SlugField(max_length=110, unique=True, blank=True, verbose_name='slug')
    descricao = models.CharField(max_length=255, blank=True, verbose_name='descrição')
    ordem = models.PositiveIntegerField(default=0, verbose_name='ordem de exibição')
    ativa = models.BooleanField(default=True, verbose_name='ativa')

    class Meta:
        """Meta options for the model."""

        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        super().save(*args, **kwargs)
