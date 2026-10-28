"""Model de Conversa — o chat de um pedido entre o cliente e a padaria."""

from django.db import models


class Conversa(models.Model):
    """Uma conversa por pedido, criada na primeira mensagem."""

    pedido = models.OneToOneField(
        'pedidos.Pedido',
        on_delete=models.CASCADE,
        related_name='conversa',
        verbose_name='pedido',
    )
    criada_em = models.DateTimeField(auto_now_add=True, verbose_name='criada em')
    atualizada_em = models.DateTimeField(auto_now_add=True, verbose_name='última mensagem em')

    class Meta:
        verbose_name = 'Conversa'
        verbose_name_plural = 'Conversas'
        ordering = ['-atualizada_em']

    def __str__(self):
        return f'Conversa do pedido #{self.pedido_id}'
