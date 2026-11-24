"""Sinais mínimos e best-effort: REST permanece fonte da verdade.

Cada publicação é agendada com transaction.on_commit; rollback nunca publica.
Falha de Redis não altera o resultado HTTP (polling do cliente cobre perdas).
"""
import asyncio
import logging
import uuid
from functools import partial

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)
ADMIN_GROUP = 'pires-admin-eventos'
TIPOS_VALIDOS = frozenset({
    'pedido.criado',
    'pedido.atualizado',
    'chat.mensagem_nova',
    'chat.leitura_atualizada',
    'notificacao.alterada',
})
LIMITE_ENVIO_SEGUNDOS = 1.0


async def _enviar_com_limite(camada, grupos, payload):
    await asyncio.wait_for(
        asyncio.gather(*(
            camada.group_send(grupo, {'type': 'realtime.event', 'payload': payload})
            for grupo in grupos
        )),
        timeout=LIMITE_ENVIO_SEGUNDOS,
    )


def _entregar(grupos, payload):
    """Entrega na janela curta do on_commit; nunca interrompe checkout/QR/chat."""
    try:
        camada = get_channel_layer()
        if camada is None:
            return
        async_to_sync(_enviar_com_limite)(camada, grupos, payload)
    except Exception:
        # Não registrar dados do Redis, segredos, payload ou informações do cliente.
        logger.warning('Sinal realtime não entregue: %s', payload['tipo'])


def publicar_evento(tipo, *, usuario_id=None, pedido_id=None, admin=False, using=None):
    """Publica somente identificadores e metadados após commit de banco."""
    if not settings.REALTIME_ENABLED or tipo not in TIPOS_VALIDOS:
        return
    grupos = set()
    if admin:
        grupos.add(ADMIN_GROUP)
    if usuario_id is not None:
        grupos.add(f'pires-usuario-{int(usuario_id)}')
    if not grupos:
        return
    payload = {
        'v': 1,
        'tipo': tipo,
        'event_id': uuid.uuid4().hex,
        'emitido_em': timezone.now().isoformat(),
    }
    if pedido_id is not None:
        payload['pedido_id'] = int(pedido_id)
    transaction.on_commit(
        partial(_entregar, tuple(sorted(grupos)), payload),
        using=using,
    )
