"""Regras do chat por pedido: prazo de encerramento, envio, leitura e não lidas."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from chat.models import Conversa, Mensagem
from chat.signals import chat_lido_pelo_cliente, mensagem_da_padaria_enviada
from pedidos.models import Pedido

STATUS_ENCERRADOS = {Pedido.Status.RETIRADO, Pedido.Status.CANCELADO}


class ChatEncerradoError(Exception):
    """O chat do pedido já está somente leitura."""


def prazo_do_chat(pedido):
    """Momento em que o chat fica somente leitura, ou None enquanto o pedido está ativo."""

    if pedido.status not in STATUS_ENCERRADOS:
        return None

    return pedido.status_atualizado_em + timedelta(hours=settings.CHAT_PRAZO_APOS_ENCERRAMENTO_HORAS)


def chat_somente_leitura(pedido):
    encerra_em = prazo_do_chat(pedido)
    return encerra_em is not None and timezone.now() >= encerra_em


def mensagens_do_pedido(pedido):
    return Mensagem.objects.filter(conversa__pedido=pedido).order_by('criada_em', 'id')


def mensagens_nao_lidas(usuario):
    """Mensagens do outro lado da conversa que o usuário ainda não leu."""

    nao_lidas = Mensagem.objects.filter(lida_em__isnull=True)

    if usuario.is_staff:
        return nao_lidas.filter(enviada_pela_padaria=False)

    return nao_lidas.filter(enviada_pela_padaria=True, conversa__pedido__usuario=usuario)


def contar_nao_lidas(usuario):
    por_pedido = [
        {'pedido': linha['conversa__pedido'], 'nao_lidas': linha['total']}
        for linha in mensagens_nao_lidas(usuario)
        .values('conversa__pedido')
        .annotate(total=Count('id'))
        .order_by('conversa__pedido')
    ]

    return {
        'total': sum(item['nao_lidas'] for item in por_pedido),
        'por_pedido': por_pedido,
    }


@transaction.atomic
def enviar_mensagem(pedido, autor, texto):
    if chat_somente_leitura(pedido):
        raise ChatEncerradoError('O chat deste pedido foi encerrado e agora é somente leitura.')

    conversa, _ = Conversa.objects.get_or_create(pedido=pedido)
    mensagem = Mensagem.objects.create(
        conversa=conversa,
        autor=autor,
        enviada_pela_padaria=autor.is_staff,
        texto=texto,
    )
    Conversa.objects.filter(pk=conversa.pk).update(atualizada_em=mensagem.criada_em)

    if mensagem.enviada_pela_padaria:
        mensagem_da_padaria_enviada.send(sender=Mensagem, mensagem=mensagem, pedido=pedido)

    return mensagem


def marcar_lidas(pedido, leitor):
    """Marca como lidas as mensagens do outro lado. Retorna quantas foram marcadas."""

    marcadas = mensagens_nao_lidas(leitor).filter(conversa__pedido=pedido).update(lida_em=timezone.now())

    if pedido.usuario_id == leitor.id and not leitor.is_staff:
        chat_lido_pelo_cliente.send(sender=Mensagem, pedido=pedido, leitor=leitor)

    return marcadas
