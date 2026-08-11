from datetime import date

from django.db.models import Sum
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from catalogo.models import Produto
from catalogo.serializers import (
    ProdutoDetailSerializer,
    ProdutoListSerializer,
    ProdutoWriteSerializer,
)
from core.permissions import IsAdminOrReadOnly
from pedidos.models import ItemPedido, Pedido


class ProdutoViewSet(ModelViewSet):
    """Cadastro e consulta de produtos."""

    queryset = (
        Produto.objects
        .select_related('categoria')
        .all()
    )

    permission_classes = [
        IsAdminOrReadOnly,
    ]

    filterset_fields = [
        'categoria',
        'ativo',
        'destaque',
    ]

    def get_serializer_class(self):
        if self.action == 'list':
            return ProdutoListSerializer

        if self.action in {
            'create',
            'update',
            'partial_update',
        }:
            return ProdutoWriteSerializer

        return ProdutoDetailSerializer

    @extend_schema(
        summary='Produtos mais vendidos',
        description=(
            'Ranking por quantidade vendida em pedidos '
            'com status retirado.'
        ),
        parameters=[
            OpenApiParameter(
                'data_inicio',
                str,
                description='Data inicial no formato YYYY-MM-DD',
                required=False,
            ),
            OpenApiParameter(
                'data_fim',
                str,
                description='Data final no formato YYYY-MM-DD',
                required=False,
            ),
            OpenApiParameter(
                'limite',
                int,
                description=(
                    'Quantidade de produtos entre 1 e 100. '
                    'O padrão é 10.'
                ),
                required=False,
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
    def mais_vendidos(self, request):
        itens = ItemPedido.objects.filter(
            pedido__status=Pedido.Status.RETIRADO,
        )

        data_inicio_str = request.query_params.get(
            'data_inicio'
        )
        data_fim_str = request.query_params.get(
            'data_fim'
        )

        try:
            data_inicio = (
                date.fromisoformat(data_inicio_str)
                if data_inicio_str
                else None
            )

            data_fim = (
                date.fromisoformat(data_fim_str)
                if data_fim_str
                else None
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

        if (
            data_inicio
            and data_fim
            and data_inicio > data_fim
        ):
            return Response(
                {
                    'detail': (
                        'data_inicio não pode ser posterior '
                        'a data_fim.'
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if data_inicio:
            itens = itens.filter(
                pedido__status_atualizado_em__date__gte=(
                    data_inicio
                )
            )

        if data_fim:
            itens = itens.filter(
                pedido__status_atualizado_em__date__lte=(
                    data_fim
                )
            )

        try:
            limite = int(
                request.query_params.get(
                    'limite',
                    10,
                )
            )
        except ValueError:
            return Response(
                {
                    'detail': (
                        'limite deve ser um número inteiro.'
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if limite < 1 or limite > 100:
            return Response(
                {
                    'detail': (
                        'limite deve estar entre 1 e 100.'
                    )
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        ranking = (
            itens
            .values(
                'produto_id',
                'produto__nome',
                'produto__codigo',
            )
            .annotate(
                quantidade_vendida=Sum(
                    'quantidade'
                )
            )
            .order_by(
                '-quantidade_vendida'
            )[:limite]
        )

        resultado = [
            {
                'produto_id': item['produto_id'],
                'produto_nome': item['produto__nome'],
                'produto_codigo': item[
                    'produto__codigo'
                ],
                'quantidade_vendida': item[
                    'quantidade_vendida'
                ],
            }
            for item in ranking
        ]

        return Response(
            {
                'criterio': (
                    'Considera apenas itens de pedidos '
                    'com status retirado.'
                ),
                'resultado': resultado,
            }
        )
