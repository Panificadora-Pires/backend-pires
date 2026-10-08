from django.contrib import admin
from django.utils import timezone

from catalogo.models import Categoria, Produto, Promocao


class SituacaoPromocaoFilter(admin.SimpleListFilter):
    title = 'situação'
    parameter_name = 'situacao'

    def lookups(self, request, model_admin):
        return (
            ('ativa', 'Ativa'),
            ('futura', 'Futura'),
            ('encerrada', 'Encerrada'),
        )

    def queryset(self, request, queryset):
        hoje = timezone.localdate()

        if self.value() == 'ativa':
            return queryset.filter(data_inicio__lte=hoje, data_fim__gte=hoje)
        if self.value() == 'futura':
            return queryset.filter(data_inicio__gt=hoje)
        if self.value() == 'encerrada':
            return queryset.filter(data_fim__lt=hoje)

        return queryset


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ordem', 'ativa']
    list_editable = ['ordem', 'ativa']
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'categoria', 'preco', 'estoque', 'estoque_baixo_display', 'ativo']
    list_filter = ['categoria', 'ativo', 'destaque']
    search_fields = ['codigo', 'nome']
    readonly_fields = ['codigo', 'slug', 'criado_em', 'atualizado_em']

    @admin.display(description='Estoque baixo', boolean=True)
    def estoque_baixo_display(self, obj):
        return obj.estoque_baixo


@admin.register(Promocao)
class PromocaoAdmin(admin.ModelAdmin):
    list_display = [
        'produto',
        'preco_original',
        'preco_promocional',
        'desconto_percentual',
        'data_inicio',
        'data_fim',
        'situacao',
    ]
    list_filter = [SituacaoPromocaoFilter, 'data_inicio', 'data_fim']
    search_fields = ['produto__nome', 'produto__codigo']
    autocomplete_fields = ['produto']
    list_select_related = ['produto']
    ordering = ['-data_inicio', 'produto__nome']
    date_hierarchy = 'data_inicio'

    fieldsets = (
        (
            'Produto e preço',
            {
                'fields': (
                    'produto',
                    'preco_promocional',
                )
            },
        ),
        (
            'Período da promoção',
            {
                'fields': (
                    'data_inicio',
                    'data_fim',
                )
            },
        ),
    )

    @admin.display(description='Preço normal', ordering='produto__preco')
    def preco_original(self, obj):
        return f'R$ {obj.produto.preco:.2f}'.replace('.', ',')

    @admin.display(description='Desconto')
    def desconto_percentual(self, obj):
        preco_original = obj.produto.preco
        if not preco_original or obj.preco_promocional >= preco_original:
            return '—'

        desconto = ((preco_original - obj.preco_promocional) / preco_original) * 100
        return f'{desconto:.0f}%'

    @admin.display(description='Situação')
    def situacao(self, obj):
        hoje = timezone.localdate()

        if obj.data_inicio > hoje:
            return 'Futura'
        if obj.data_fim < hoje:
            return 'Encerrada'
        return 'Ativa'
