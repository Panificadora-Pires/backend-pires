"""
Receiver que escuta o signal `pedido_ficou_pronto` (disparado pelo app
`pedidos`) e cria a notificação correspondente para o aluno.
"""

from django.dispatch import receiver

from pedidos.signals import pedido_ficou_pronto

from .models import Notificacao


@receiver(pedido_ficou_pronto)
def criar_notificacao_pedido_pronto(sender, pedido, **kwargs):
    Notificacao.objects.create(
        usuario=pedido.usuario,
        pedido=pedido,
        mensagem=f'Seu pedido #{pedido.id} está pronto para retirada! Mostre seu QR Code no balcão.',
    )
