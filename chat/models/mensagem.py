"""Model de Mensagem do chat por pedido."""

from django.conf import settings
from django.db import models


class Mensagem(models.Model):
    """
    Mensagem de texto puro (sem HTML e sem anexos).

    `enviada_pela_padaria` é gravado no envio a partir de `is_staff` do autor, para
    o lado da conversa não mudar se o usuário perder ou ganhar acesso de administrador.
    """

    conversa = models.ForeignKey(
        'chat.Conversa',
        on_delete=models.CASCADE,
        related_name='mensagens',
        verbose_name='conversa',
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='mensagens_chat',
        verbose_name='autor',
    )
    enviada_pela_padaria = models.BooleanField(default=False, verbose_name='enviada pela padaria')
    texto = models.TextField(verbose_name='texto')
    criada_em = models.DateTimeField(auto_now_add=True, verbose_name='enviada em')
    lida_em = models.DateTimeField(null=True, blank=True, verbose_name='lida em')

    class Meta:
        verbose_name = 'Mensagem'
        verbose_name_plural = 'Mensagens'
        ordering = ['criada_em', 'id']
        indexes = [
            # Contagem de não lidas de cada lado da conversa.
            models.Index(fields=['enviada_pela_padaria', 'lida_em'], name='chat_msg_nao_lidas_idx'),
            models.Index(fields=['conversa', 'criada_em'], name='chat_msg_conversa_data_idx'),
        ]

    def __str__(self):
        lado = 'Padaria' if self.enviada_pela_padaria else 'Cliente'
        return f'{lado} — {self.texto[:40]}'
