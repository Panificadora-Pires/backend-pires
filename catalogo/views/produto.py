from datetime import date

from django.db.models import Sum
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from catalogo.models import Produto
from catalogo.serializers import ProdutoDetailSerializer, ProdutoListSerializer, ProdutoWriteSerializer
from core.permissions import IsAdminOrReadOnly
from pedidos.models import ItemPedido, Pedido


class ProdutoViewSet(ModelViewSet):
    """RF02 — Cadastro de produto / RF09 — Consulta de cardápio do dia."""

    queryset = Produto.objects.select_related('categoria').all()
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['categoria', 'ativo', 'destaque']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProdutoListSerializer
        if self.action in {'create', 'update', 'partial_update'}:
            return ProdutoWriteSerializer
        return ProdutoDetailSerializer

    @extend_schema(
        summary='Produtos mais vendidos (RF12)',
        description=(
            'Ranking de produtos por quantidade vendida em pedidos retirados. '
            'Sem data_inicio/data_fim, considera todo o histórico.'
        ),
        parameters=[
            OpenApiParameter('data_inicio', str, description='Data inicial (YYYY-MM-DD)', required=False),
            OpenApiParameter('data_fim', str, description='Data final (YYYY-MM-DD)', required=False),
            OpenApiParameter('limite', int, description='Quantidade de produtos a retornar (padrão 10)', required=False),  # ruff:ignore[line-too-long]
        ],
        responses={200: None, 400: None, 403: None},
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def mais_vendidos(self, request):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Apenas a administração pode acessar relatórios.'},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        itens = ItemPedido.objects.filter(pedido__status=Pedido.Status.RETIRADO)

        data_inicio_str = request.query_params.get('data_inicio')
        data_fim_str = request.query_params.get('data_fim')
        try:
            if data_inicio_str:
                itens = itens.filter(pedido__status_atualizado_em__date__gte=date.fromisoformat(data_inicio_str))
            if data_fim_str:
                itens = itens.filter(pedido__status_atualizado_em__date__lte=date.fromisoformat(data_fim_str))
        except ValueError:
            return Response(
                {'detail': 'Datas em formato inválido. Use YYYY-MM-DD.'},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            limite = int(request.query_params.get('limite', 10))
        except ValueError:
            return Response(
                {'detail': 'limite deve ser um número inteiro.'}, status=http_status.HTTP_400_BAD_REQUEST
            )

        ranking = (
            itens.values('produto_id', 'produto__nome', 'produto__codigo')
            .annotate(quantidade_vendida=Sum('quantidade'))
            .order_by('-quantidade_vendida')[:limite]
        )

        resultado = [
            {
                'produto_id': item['produto_id'],
                'produto_nome': item['produto__nome'],
                'produto_codigo': item['produto__codigo'],
                'quantidade_vendida': item['quantidade_vendida'],
            }
            for item in ranking
        ]

        return Response(
            {'criterio': 'Considera apenas itens de pedidos com status "retirado".', 'resultado': resultado}
        )
