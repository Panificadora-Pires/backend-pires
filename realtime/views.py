"""Emissão autenticada de ticket descartável para o handshake WebSocket."""
import logging
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .tickets import TicketUnavailable, emitir_ticket

logger = logging.getLogger(__name__)


class RealtimeTicketView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'realtime_ticket'

    @extend_schema(
        summary='Emite ticket de uso único para WebSocket (recurso opt-in)',
        request=None,
        responses={200: dict, 503: dict},
    )
    def post(self, request):
        if not settings.REALTIME_ENABLED:
            logger.warning("ticket_hml reason=realtime_disabled")
            return Response(
                {'detail': 'Atualizações em tempo real indisponíveis.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not request.user.is_active:
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            ticket = emitir_ticket(request.user)
        except TicketUnavailable as exc:
            # Não registrar exceção, URL Redis, ticket, credenciais nem usuário.
            cause_type = type(exc.__cause__).__name__ if exc.__cause__ else "none"
            logger.warning(
                "ticket_hml reason=emission_failed cause_type=%s",
                cause_type,
            )
            return Response(
                {'detail': 'Atualizações em tempo real indisponíveis.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        resposta = Response({
            'ticket': ticket,
            'expires_in': settings.REALTIME_TICKET_TTL_SECONDS,
            'protocol': 'pires.v1',
            'ws_path': '/ws/v1/events/',
        })
        resposta['Cache-Control'] = 'no-store'
        return resposta
