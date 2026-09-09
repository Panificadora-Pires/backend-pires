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

    def save_formset(self, request, form, formset, change):
        """Preenche automaticamente o preço do produto ao criar itens."""

        instances = formset.save(commit=False)

        # Remove itens marcados para exclusão.
        for instance in formset.deleted_objects:
            instance.delete()

        # Salva os itens novos/alterados.
        for instance in instances:
            if isinstance(instance, ItemPedido):
                # O preço é definido automaticamente apenas para itens novos.
                if instance.pk is None and instance.produto_id:
                    instance.preco_unitario = instance.produto.preco_atual

            instance.save()

        formset.save_m2m()
