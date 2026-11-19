"""Pontos de emissão que cobrem checkout, pagamento, QR, expiração e chat.

`post_save` cobre os fluxos que chamam Model.save(); bulk QuerySet.update
não envia sinais, portanto a leitura de chat/notificações é instrumentada
explicitamente onde usa update().
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from chat.models import Mensagem
from notificacoes.models import Notificacao
from pedidos.models import Pedido

from .events import publicar_evento

CAMPOS_PEDIDO_RELEVANTES = frozenset({
    'status',
    'status_atualizado_em',
    'status_pagamento',
    'pagamento_expira_em',
    'mercadopago_status',
    'mercadopago_payment_id',
    'mercadopago_order_id',
})


@receiver(post_save, sender=Pedido, dispatch_uid='pires.realtime.pedido.salvo')
def pedido_salvo(sender, instance, created, raw, using, update_fields, **kwargs):
    if raw:
        return
    if not created and update_fields is not None and not (CAMPOS_PEDIDO_RELEVANTES & set(update_fields)):
        return
    publicar_evento(
        'pedido.criado' if created else 'pedido.atualizado',
        usuario_id=instance.usuario_id,
        pedido_id=instance.pk,
        admin=True,
        using=using,
    )


@receiver(post_save, sender=Mensagem, dispatch_uid='pires.realtime.chat.enviado')
def mensagem_salva(sender, instance, created, raw, using, **kwargs):
    if raw or not created:
        return
    # A consulta é limitada ao ID da conversa; não envia texto do chat.
    from chat.models import Conversa

    pedido = Conversa.objects.using(using).filter(pk=instance.conversa_id).values(
        'pedido_id', 'pedido__usuario_id'
    ).first()
    if not pedido:
        return
    publicar_evento(
        'chat.mensagem_nova',
        pedido_id=pedido['pedido_id'],
        usuario_id=pedido['pedido__usuario_id'],
        admin=True,
        using=using,
    )


@receiver(post_save, sender=Notificacao, dispatch_uid='pires.realtime.notificacao.salva')
def notificacao_salva(sender, instance, raw, using, **kwargs):
    if raw:
        return
    publicar_evento(
        'notificacao.alterada',
        usuario_id=instance.usuario_id,
        pedido_id=instance.pedido_id,
        using=using,
    )
