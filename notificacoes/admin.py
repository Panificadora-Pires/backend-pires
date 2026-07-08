from django.contrib import admin

from .models import Notificacao


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'mensagem', 'lida', 'criada_em']
    list_filter = ['lida']
    search_fields = ['usuario__email', 'mensagem']
