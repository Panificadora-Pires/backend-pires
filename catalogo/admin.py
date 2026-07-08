from django.contrib import admin

from catalogo.models import Categoria, Produto


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
