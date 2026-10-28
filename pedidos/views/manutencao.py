"""Endpoints de manutenção chamados por agendadores externos e monitoramento."""

import hmac
import logging

from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from pedidos.services.expiracao import expirar_pedidos

logger = logging.getLogger(__name__)


class ExpirarPedidosView(APIView):
    """Executa as regras de expiração de pedidos. Protegido por token de manutenção."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'manutencao'

    @extend_schema(
        summary='Expirar pedidos (agendador)',
        description=(
            'Cancela pedidos prontos não retirados, checkouts online sem pagamento e, se configurado, '
            'pedidos confirmados parados. Exige o cabeçalho `X-Manutencao-Token`.'
        ),
        request=None,
        responses={200: None, 401: None, 503: None},
    )
    def post(self, request):
        esperado = settings.MANUTENCAO_TOKEN

        if not esperado:
            return Response(
                {'detail': 'Manutenção automática não está configurada.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        recebido = request.headers.get('X-Manutencao-Token', '')

        if not hmac.compare_digest(recebido.encode('utf-8'), esperado.encode('utf-8')):
            logger.warning('Manutenção: token inválido recebido.')
            return Response(
                {'detail': 'Token de manutenção inválido.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        resultado = expirar_pedidos()
        return Response(resultado.como_dict(), status=status.HTTP_200_OK)


class HealthView(APIView):
    """Verificação simples de saúde (aplicação + banco), usada por monitoramento."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'health'

    @extend_schema(summary='Saúde da API', responses={200: None, 503: None})
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
        except Exception:  # noqa: BLE001 - qualquer falha de banco significa indisponível
            logger.exception('Health check falhou ao consultar o banco.')
            return Response({'status': 'erro'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({'status': 'ok'})
