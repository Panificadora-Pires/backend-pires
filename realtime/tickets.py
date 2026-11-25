"""Tickets WS efêmeros, armazenados e consumidos atomicamente no Redis."""
import hashlib
import re
import secrets

from django.conf import settings


class TicketUnavailable(Exception):
    """Falha fechada: indisponibilidade do Redis ou do ticket."""


def _client():
    import redis

    if not settings.REALTIME_ENABLED or not settings.REALTIME_REDIS_URL:
        raise TicketUnavailable('Transporte em tempo real desativado.')
    return redis.Redis.from_url(
        settings.REALTIME_REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _key(ticket):
    digest = hashlib.sha256(ticket.encode('ascii')).hexdigest()
    return f'pires:realtime:ticket:{digest}'


def emitir_ticket(user):
    """Emite apenas para contas ativas. O token bruto nunca é persistido."""
    if not settings.REALTIME_ENABLED or not user.is_active:
        raise TicketUnavailable('Transporte indisponível.')
    papel = 'admin' if user.is_staff else 'usuario'
    ticket = secrets.token_urlsafe(32)
    try:
        criado = _client().set(
            _key(ticket),
            f'{user.pk}:{papel}',
            ex=settings.REALTIME_TICKET_TTL_SECONDS,
            nx=True,
        )
        if not criado:
            raise TicketUnavailable('Não foi possível reservar um ticket único.')
    except TicketUnavailable:
        raise
    except Exception as error:
        raise TicketUnavailable('Não foi possível emitir o ticket.') from error
    return ticket


def consumir_ticket(ticket):
    """GETDEL Redis 6.2+: impede replay entre processos, mesmo simultâneo."""
    if (
        not settings.REALTIME_ENABLED
        or not isinstance(ticket, str)
        or not re.fullmatch(r'[A-Za-z0-9_-]{40,128}', ticket)
    ):
        return None
    try:
        resposta = _client().getdel(_key(ticket))
    except Exception as error:
        raise TicketUnavailable('Redis indisponível ao consumir ticket.') from error
    if not resposta:
        return None
    partes = resposta.split(':', maxsplit=1)
    if len(partes) != 2 or not partes[0].isdigit() or partes[1] not in ('admin', 'usuario'):
        return None
    return int(partes[0]), partes[1]
