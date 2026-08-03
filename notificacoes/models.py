"""
Model de Notificação — avisos para o aluno (ex: "seu pedido está pronto").

Não existe infraestrutura de push/WebSocket no template (isso exigiria
Celery/Redis/Channels), então a notificação aqui funciona por polling: o
frontend consulta periodicamente `GET /api/notificacoes/?lida=false` e mostra
um sininho/contador. É uma solução honesta pro escopo do projeto — dá pra
evoluir pra push de verdade depois, sem quebrar essa API.
"""

from django.conf import settings
from django.db import models


class Notificacao(models.Model):
    """Notificação em app para um usuário, opcionalmente ligada a um pedido."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificacoes', verbose_name='usuário'
    )
    pedido = models.ForeignKey(
        'pedidos.Pedido',
        on_delete=models.CASCADE,
        related_name='notificacoes',
        null=True,
        blank=True,
        verbose_name='pedido relacionado',
    )
    mensagem = models.CharField(max_length=255, verbose_name='mensagem')
    lida = models.BooleanField(default=False, verbose_name='lida')
    criada_em = models.DateTimeField(auto_now_add=True, verbose_name='criada em')

    class Meta:
        """Meta options for the model."""

        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-criada_em']

    def __str__(self):
        return f'{self.usuario} — {self.mensagem}'
