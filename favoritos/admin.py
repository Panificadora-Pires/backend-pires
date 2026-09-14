from django.contrib import admin

from .models import Favorito


@admin.register(Favorito)
class FavoritoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'produto', 'criado_em')
    search_fields = ('usuario__email', 'usuario__name', 'produto__nome')
    list_select_related = ('usuario', 'produto')
    readonly_fields = ('criado_em',)
