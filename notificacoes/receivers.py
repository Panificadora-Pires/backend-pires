"""
Receivers que criam notificações para o aluno a partir de signals de outros apps:
`pedido_ficou_pronto` (app `pedidos`) e as mensagens do chat (app `chat`).
"""

from django.dispatch import receiver

from chat.signals import chat_lido_pelo_cliente, mensagem_da_padaria_enviada
from pedidos.signals import pedido_ficou_pronto

from .models import Notificacao


@receiver(pedido_ficou_pronto)
def criar_notificacao_pedido_pronto(sender, pedido, **kwargs):
    Notificacao.objects.create(
        usuario=pedido.usuario,
        pedido=pedido,
        mensagem=f'Seu pedido #{pedido.id} está pronto para retirada! Mostre seu QR Code no balcão.',
    )


def mensagem_notificacao_chat(pedido):
    return f'Nova mensagem da padaria sobre o pedido #{pedido.id}.'


@receiver(mensagem_da_padaria_enviada)
def criar_notificacao_mensagem_chat(sender, mensagem, pedido, **kwargs):
    # Uma notificação não lida por pedido basta: várias mensagens seguidas não lotam o sininho.
    Notificacao.objects.get_or_create(
        usuario=pedido.usuario,
        pedido=pedido,
        mensagem=mensagem_notificacao_chat(pedido),
        lida=False,
    )


@receiver(chat_lido_pelo_cliente)
def marcar_notificacao_chat_lida(sender, pedido, leitor, **kwargs):
    Notificacao.objects.filter(
        usuario=leitor,
        pedido=pedido,
        mensagem=mensagem_notificacao_chat(pedido),
        lida=False,
    ).update(lida=True)
