from django.contrib import admin

from chat.models import Conversa, Mensagem


class MensagemInline(admin.TabularInline):
    model = Mensagem
    extra = 0
    fields = ['criada_em', 'enviada_pela_padaria', 'autor', 'texto', 'lida_em']
    readonly_fields = fields
    can_delete = False


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):
    list_display = ['pedido', 'criada_em', 'atualizada_em']
    search_fields = ['pedido__id', 'pedido__usuario__email']
    readonly_fields = ['pedido', 'criada_em', 'atualizada_em']
    inlines = [MensagemInline]
