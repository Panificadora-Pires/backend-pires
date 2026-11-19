"""Emissão autenticada de ticket descartável para o handshake WebSocket."""
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .tickets import TicketUnavailable, emitir_ticket


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
            return Response(
                {'detail': 'Atualizações em tempo real indisponíveis.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not request.user.is_active:
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            ticket = emitir_ticket(request.user)
        except TicketUnavailable:
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
