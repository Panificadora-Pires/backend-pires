from datetime import date
from decimal import Decimal

from django.db.models import F, Sum
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.permissions import IsOwnerOrAdmin
from pedidos.models import ItemPedido, Pedido
from pedidos.serializers import PedidoSerializer, PedidoStatusUpdateSerializer, RetiradaPorQRCodeSerializer
from pedidos.utils import gerar_qrcode_base64


class PedidoViewSet(ModelViewSet):
    """RF04 — criação de pedido / RF07 — gestão de status / RF10 — acompanhamento."""

    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filterset_fields = ['status']

    def get_queryset(self):
        """Aluno só vê os próprios pedidos; administração vê todos (RF10)."""
        usuario = self.request.user
        queryset = Pedido.objects.all().prefetch_related('itens__produto').order_by('-data')
        if usuario.is_staff:
            return queryset
        return queryset.filter(usuario=usuario)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @extend_schema(
        summary='Alterar status do pedido',
        description='Avança o status do pedido seguindo a RN04. Apenas a administração pode chamar.',
        request=PedidoStatusUpdateSerializer,
        responses={200: PedidoSerializer, 400: None, 403: None},
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def alterar_status(self, request, pk=None):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Apenas a administração pode alterar o status do pedido.'},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        pedido = self.get_object()
        serializer = PedidoStatusUpdateSerializer(pedido, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(PedidoSerializer(pedido).data, status=http_status.HTTP_200_OK)

    @extend_schema(
        summary='Obter QR Code de retirada do pedido',
        description='Retorna o QR Code (PNG em base64) que o aluno mostra no balcão para retirar o pedido.',
        responses={200: None},
    )
    @action(detail=True, methods=['get'])
    def qrcode(self, request, pk=None):
        pedido = self.get_object()
        conteudo = str(pedido.codigo_retirada)
        return Response(
            {
                'codigo_retirada': conteudo,
                'qrcode_base64': gerar_qrcode_base64(conteudo),
            }
        )

    @extend_schema(
        summary='Retirar pedido via QR Code',
        description=(
            'Usado pela administração no balcão: lê o QR Code do aluno e, se o pedido '
            'estiver "pronto", muda o status para "retirado".'
        ),
        request=RetiradaPorQRCodeSerializer,
        responses={200: PedidoSerializer, 400: None, 403: None},
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def retirar_via_qrcode(self, request):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Apenas a administração pode confirmar retiradas.'},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        serializer = RetiradaPorQRCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save()

        return Response(PedidoSerializer(pedido).data, status=http_status.HTTP_200_OK)

    @extend_schema(
        summary='Relatório de vendas por período (RF11)',
        description=(
            'Soma as vendas de pedidos com status "retirado" dentro do período informado. '
            'Apenas pedidos efetivamente retirados contam como venda concluída.'
        ),
        parameters=[
            OpenApiParameter('data_inicio', str, description='Data inicial (formato YYYY-MM-DD)', required=True),
            OpenApiParameter('data_fim', str, description='Data final (formato YYYY-MM-DD)', required=True),
        ],
        responses={200: None, 400: None, 403: None},
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def relatorio_vendas(self, request):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Apenas a administração pode acessar relatórios.'},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        data_inicio_str = request.query_params.get('data_inicio')
        data_fim_str = request.query_params.get('data_fim')

        if not data_inicio_str or not data_fim_str:
            return Response(
                {'detail': 'Informe data_inicio e data_fim (formato YYYY-MM-DD).'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            data_inicio = date.fromisoformat(data_inicio_str)
            data_fim = date.fromisoformat(data_fim_str)
        except ValueError:
            return Response(
                {'detail': 'Datas em formato inválido. Use YYYY-MM-DD.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        pedidos_periodo = Pedido.objects.filter(
            status=Pedido.Status.RETIRADO,
            status_atualizado_em__date__gte=data_inicio,
            status_atualizado_em__date__lte=data_fim,
        )

        total_pedidos = pedidos_periodo.count()

        agregado = ItemPedido.objects.filter(pedido__in=pedidos_periodo).aggregate(
            total_vendido=Sum(F('preco_unitario') * F('quantidade'))
        )
        total_vendido = agregado['total_vendido'] or Decimal('0.00')
        ticket_medio = (total_vendido / total_pedidos) if total_pedidos else Decimal('0.00')

        return Response(
            {
                'criterio': 'Considera apenas pedidos com status "retirado" dentro do período informado.',
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'total_pedidos': total_pedidos,
                'total_vendido': round(total_vendido, 2),
                'ticket_medio': round(ticket_medio, 2),
            }
        )
