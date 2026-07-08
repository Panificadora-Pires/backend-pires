from django.contrib import admin

from pedidos.models import ItemPedido, Pedido


class ItemPedidoInline(admin.TabularInline):
    """Permite ver/editar os itens de um pedido direto na tela do pedido."""

    model = ItemPedido
    extra = 0
    readonly_fields = ['preco_unitario']


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'status', 'data', 'total']
    list_filter = ['status']
    search_fields = ['usuario__email', 'usuario__name', 'codigo_retirada']
    readonly_fields = ['codigo_retirada', 'data']
    inlines = [ItemPedidoInline]
