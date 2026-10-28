from django.contrib import admin

from chatbot.models import PerguntaFrequente


@admin.register(PerguntaFrequente)
class PerguntaFrequenteAdmin(admin.ModelAdmin):
    list_display = ['pergunta', 'chave', 'ordem', 'sugerida', 'ativa', 'atualizada_em']
    list_editable = ['ordem', 'sugerida', 'ativa']
    list_filter = ['ativa', 'sugerida']
    search_fields = ['pergunta', 'chave', 'palavras_chave', 'resposta']
