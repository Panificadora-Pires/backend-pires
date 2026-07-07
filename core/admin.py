"""
Django admin customization.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from core import models


class UserAdmin(BaseUserAdmin):
    """Define the admin pages for users."""

    ordering = ('id',)
    list_display = ('email', 'name')
    search_fields = ('email', 'name', 'groups__name')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Info'), {'fields': ('name',)}),
        (
            _('Permissions'),
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                )
            },
        ),
        (_('Important dates'), {'fields': ('last_login',)}),
        (_('Groups'), {'fields': ('groups',)}),
        (_('User Permissions'), {'fields': ('user_permissions',)}),
    )
    readonly_fields = ['last_login']
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'password1',
                    'password2',
                    'name',
                    'is_active',
                    'is_staff',
                    'is_superuser',
                ),
            },
        ),
    )


admin.site.register(models.User, UserAdmin)


class ItemPedidoInline(admin.TabularInline):
    """Permite ver/editar os itens de um pedido direto na tela do pedido."""

    model = models.ItemPedido
    extra = 0
    readonly_fields = ['preco_unitario']


@admin.register(models.Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'categoria', 'preco', 'estoque', 'ativo']
    list_filter = ['categoria', 'ativo']
    search_fields = ['nome']


@admin.register(models.Promocao)
class PromocaoAdmin(admin.ModelAdmin):
    list_display = ['produto', 'preco_promocional', 'data_inicio', 'data_fim']
    list_filter = ['data_inicio', 'data_fim']
    search_fields = ['produto__nome']


@admin.register(models.Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'status', 'data', 'total']
    list_filter = ['status']
    search_fields = ['usuario__email', 'usuario__name']
    inlines = [ItemPedidoInline]
