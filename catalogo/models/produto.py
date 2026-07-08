"""
Model de Produto (itens vendidos na cantina).
"""

from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from catalogo.validators import validar_tamanho_imagem, validar_tipo_imagem

from .categoria import Categoria


class Produto(models.Model):
    """Produto disponível para venda/reserva na cantina (RF02, RF09)."""

    class UnidadeMedida(models.TextChoices):
        UNIDADE = 'unidade', 'Unidade'
        QUILO = 'kg', 'Quilo'
        GRAMA = 'g', 'Grama'
        LITRO = 'l', 'Litro'
        MILILITRO = 'ml', 'Mililitro'

    codigo = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        verbose_name='código (SKU)',
        help_text='Gerado automaticamente se deixado em branco.',
    )
    nome = models.CharField(max_length=255, verbose_name='nome')
    slug = models.SlugField(max_length=270, unique=True, blank=True, verbose_name='slug')
    descricao = models.TextField(blank=True, verbose_name='descrição')
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='produtos', verbose_name='categoria'
    )
    imagem = models.ImageField(
        upload_to='produtos/',
        blank=True,
        null=True,
        verbose_name='imagem',
        validators=[validar_tipo_imagem, validar_tamanho_imagem],
    )
    unidade_medida = models.CharField(
        max_length=10,
        choices=UnidadeMedida.choices,
        default=UnidadeMedida.UNIDADE,
        verbose_name='unidade de medida',
    )
    preco = models.DecimalField(max_digits=7, decimal_places=2, verbose_name='preço de venda')
    preco_custo = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='preço de custo',
        help_text='Uso interno da administração. Nunca é exposto ao aluno.',
    )
    estoque = models.PositiveIntegerField(default=0, verbose_name='estoque')
    estoque_minimo = models.PositiveIntegerField(
        default=0, verbose_name='estoque mínimo', help_text='Usado para alertar necessidade de reposição.'
    )
    destaque = models.BooleanField(default=False, verbose_name='destaque no cardápio')
    ativo = models.BooleanField(default=True, verbose_name='ativo')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='atualizado em')

    class Meta:
        """Meta options for the model."""

        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['categoria__ordem', 'nome']

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        if not self.codigo:
            self.codigo = self._gerar_codigo()
        super().save(*args, **kwargs)

    def _gerar_codigo(self):
        """Gera um código sequencial simples do tipo PRD0001."""
        ultimo = Produto.objects.order_by('-id').first()
        proximo_numero = (ultimo.id + 1) if ultimo else 1
        return f'PRD{proximo_numero:04d}'

    @property
    def estoque_baixo(self):
        """Indica se o estoque está no ou abaixo do mínimo definido (alerta de reposição)."""
        return self.estoque <= self.estoque_minimo

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
