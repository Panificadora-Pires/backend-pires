from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.permissions import (
    IsAdminUser,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from core.permissions import IsOwnerOrAdmin
from pedidos.models import ItemPedido, Pedido
from pedidos.serializers import (
    PedidoSerializer,
    PedidoStatusUpdateSerializer,
    RetiradaPorQRCodeSerializer,
)
from pedidos.utils import gerar_qrcode_base64


class PedidoViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    """
    Criação e consulta de pedidos.

    Alterações de status são feitas somente pelas ações
    específicas, seguindo as regras de negócio.
    """

    serializer_class = PedidoSerializer
    permission_classes = [
        IsAuthenticated,
        IsOwnerOrAdmin,
    ]
    filterset_fields = [
        'status',
    ]

    def get_queryset(self):
        usuario = self.request.user

        queryset = (
            Pedido.objects
            .select_related('usuario')
            .prefetch_related(
                'itens__produto',
            )
            .order_by('-data')
        )

        if usuario.is_staff:
            return queryset

        return queryset.filter(
            usuario=usuario,
        )

    @extend_schema(
        summary='Alterar status do pedido',
        description=(
            'Altera o status seguindo as transições da RN04. '
            'Disponível somente para administradores.'
        ),
        request=PedidoStatusUpdateSerializer,
        responses={
            200: PedidoSerializer,
            400: None,
            403: None,
            404: None,
        },
    )
    @action(
        detail=True,
        methods=['patch'],
        permission_classes=[IsAdminUser],
    )
    def alterar_status(self, request, pk=None):
        with transaction.atomic():
            queryset = (
                self.filter_queryset(
                    self.get_queryset()
                )
                .select_for_update()
            )

            pedido = get_object_or_404(
                queryset,
                pk=pk,
            )

            serializer = PedidoStatusUpdateSerializer(
                pedido,
                data=request.data,
                partial=True,
            )
            serializer.is_valid(
                raise_exception=True,
            )
            serializer.save()

        return Response(
            self.get_serializer(pedido).data,
            status=http_status.HTTP_200_OK,
        )

    @extend_schema(
        summary='Obter QR Code de retirada',
        description=(
            'Retorna o QR Code que o aluno apresenta '
            'no balcão para retirar o pedido.'
        ),
        responses={
            200: None,
            404: None,
        },
    )
    @action(
        detail=True,
        methods=['get'],
    )
    def qrcode(self, request, pk=None):
        pedido = self.get_object()
        conteudo = str(
            pedido.codigo_retirada,
        )

        return Response(
            {
                'codigo_retirada': conteudo,
                'qrcode_base64': gerar_qrcode_base64(
                    conteudo
                ),
            }
        )

    @extend_schema(
        summary='Retirar pedido via QR Code',
        description=(
            'Confirma a retirada de um pedido pronto. '
            'Disponível somente para administradores.'
        ),
        request=RetiradaPorQRCodeSerializer,
        responses={
            200: PedidoSerializer,
            400: None,
            403: None,
        },
    )
    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAdminUser],
    )
    def retirar_via_qrcode(self, request):
        serializer = RetiradaPorQRCodeSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        pedido = serializer.save()

        return Response(
            self.get_serializer(pedido).data,
            status=http_status.HTTP_200_OK,
        )

    @extend_schema(
        summary='Relatório de vendas por período',
        description=(
            'Soma pedidos retirados dentro do período. '
            'Somente pedidos efetivamente retirados '
            'são considerados vendas.'
        ),
        parameters=[
            OpenApiParameter(
                'data_inicio',
                str,
                description='Data inicial no formato YYYY-MM-DD',
                required=True,
            ),
            OpenApiParameter(
                'data_fim',
                str,
                description='Data final no formato YYYY-MM-DD',
                required=True,
            ),
        ],
        responses={
            200: None,
            400: None,
            403: None,
        },
    )
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAdminUser],
    )
    def relatorio_vendas(self, request):
        data_inicio_str = request.query_params.get(
            'data_inicio'
        )
        data_fim_str = request.query_params.get(
            'data_fim'
        )

        if not data_inicio_str or not data_fim_str:
            return Response(
                {
                    'detail': (
                        'Informe data_inicio e data_fim '
                        'no formato YYYY-MM-DD.'
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            data_inicio = date.fromisoformat(
                data_inicio_str
            )
            data_fim = date.fromisoformat(
                data_fim_str
            )
        except ValueError:
            return Response(
                {
                    'detail': (
                        'Datas em formato inválido. '
                        'Use YYYY-MM-DD.'
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if data_inicio > data_fim:
            return Response(
                {
                    'detail': (
                        'data_inicio não pode ser posterior '
                        'a data_fim.'
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        pedidos_periodo = Pedido.objects.filter(
            status=Pedido.Status.RETIRADO,
            status_atualizado_em__date__gte=data_inicio,
            status_atualizado_em__date__lte=data_fim,
        )

        total_pedidos = pedidos_periodo.count()

        agregado = ItemPedido.objects.filter(
            pedido__in=pedidos_periodo,
        ).aggregate(
            total_vendido=Sum(
                F('preco_unitario')
                * F('quantidade')
            )
        )

        total_vendido = (
            agregado['total_vendido']
            or Decimal('0.00')
        )

        ticket_medio = (
            total_vendido / total_pedidos
            if total_pedidos
            else Decimal('0.00')
        )

        return Response(
            {
                'criterio': (
                    'Considera apenas pedidos retirados '
                    'dentro do período informado.'
                ),
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'total_pedidos': total_pedidos,
                'total_vendido': round(
                    total_vendido,
                    2,
                ),
                'ticket_medio': round(
                    ticket_medio,
                    2,
                ),
            }
        )
