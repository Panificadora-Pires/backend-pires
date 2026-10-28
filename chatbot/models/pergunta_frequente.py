"""Model de PerguntaFrequente — conteúdo editável da FAQ do chatbot."""

from django.core.exceptions import ValidationError
from django.db import models

# Intenções respondidas pelo código (consultam dados do usuário); não podem virar FAQ.
CHAVES_RESERVADAS = {'inicio', 'fallback', 'meus_pedidos', 'falar_com_padaria', 'disponibilidade'}


class PerguntaFrequente(models.Model):
    """Pergunta da FAQ respondida pelo chatbot quando o texto do cliente bate com as palavras-chave."""

    chave = models.SlugField(
        max_length=50,
        unique=True,
        verbose_name='chave',
        help_text='Identificador usado pelos botões (ex.: retirada). Sem espaços nem acentos.',
    )
    pergunta = models.CharField(
        max_length=120,
        verbose_name='pergunta',
        help_text='Texto do botão de sugestão (ex.: "Como funciona a retirada?").',
    )
    palavras_chave = models.TextField(
        verbose_name='palavras-chave',
        help_text=(
            'Separadas por vírgula, sem diferença entre maiúsculas e acentos. '
            'Use * no fim para aceitar variações (cancel* vale para cancelar e cancelamento).'
        ),
    )
    resposta = models.TextField(
        verbose_name='resposta',
        help_text=(
            'Texto puro. Use {minutos_retirada} e {minutos_pagamento} para mostrar os prazos configurados no sistema.'
        ),
    )
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name='ordem')
    sugerida = models.BooleanField(
        default=True,
        verbose_name='sugerida',
        help_text='Aparece como botão na abertura do chatbot.',
    )
    ativa = models.BooleanField(default=True, verbose_name='ativa')
    atualizada_em = models.DateTimeField(auto_now=True, verbose_name='atualizada em')

    class Meta:
        verbose_name = 'Pergunta frequente'
        verbose_name_plural = 'Perguntas frequentes'
        ordering = ['ordem', 'id']

    def __str__(self):
        return self.pergunta

    def clean(self):
        if self.chave in CHAVES_RESERVADAS:
            raise ValidationError({'chave': 'Esta chave é usada pelo próprio chatbot. Escolha outra.'})

    def lista_palavras_chave(self):
        return [palavra.strip() for palavra in self.palavras_chave.split(',') if palavra.strip()]
