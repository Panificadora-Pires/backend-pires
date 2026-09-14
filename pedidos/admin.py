from django.contrib import admin
from django.core.exceptions import ValidationError

from pedidos.models import ItemPedido, Pedido
from pedidos.services.pagamentos import MercadoPagoError, preparar_cancelamento_financeiro
from pedidos.services.pedido import devolver_estoque_pedido


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0
    readonly_fields = ['preco_unitario']


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'usuario',
        'status',
        'forma_pagamento',
        'status_pagamento',
        'data',
        'total',
    ]
    list_filter = ['status', 'forma_pagamento', 'status_pagamento']
    search_fields = [
        'usuario__email',
        'usuario__name',
        'codigo_retirada',
        'mercadopago_payment_id',
    ]
    readonly_fields = [
        'codigo_retirada',
        'checkout_id',
        'data',
        'mercadopago_payment_id',
        'mercadopago_status',
        'mercadopago_status_detail',
        'pix_qr_code',
        'pix_qr_code_base64',
        'estoque_devolvido',
    ]
    inlines = [ItemPedidoInline]

    def save_model(self, request, obj, form, change):
        anterior = None
        if change and obj.pk:
            anterior = Pedido.objects.get(pk=obj.pk)

        if (
            anterior is not None
            and anterior.status != Pedido.Status.CANCELADO
            and obj.status == Pedido.Status.CANCELADO
        ):
            try:
                anterior = preparar_cancelamento_financeiro(anterior)
                obj.status_pagamento = anterior.status_pagamento
            except MercadoPagoError as exc:
                raise ValidationError(
                    f'O pedido não foi cancelado porque o pagamento não pôde ser conciliado: {exc}'
                ) from exc

        if (
            obj.status == Pedido.Status.RETIRADO
            and obj.forma_pagamento == Pedido.FormaPagamento.DINHEIRO
        ):
            obj.status_pagamento = Pedido.StatusPagamento.APROVADO

        super().save_model(request, obj, form, change)

        if (
            anterior is not None
            and anterior.status != Pedido.Status.CANCELADO
            and obj.status == Pedido.Status.CANCELADO
        ):
            devolver_estoque_pedido(obj)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in formset.deleted_objects:
            instance.delete()
        for instance in instances:
            if isinstance(instance, ItemPedido):
                if instance.pk is None and instance.produto_id:
                    instance.preco_unitario = instance.produto.preco_atual
            instance.save()
        formset.save_m2m()
