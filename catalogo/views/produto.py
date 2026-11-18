from datetime import date

from django.db.models import BooleanField, Case, Count, DecimalField, Exists, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from catalogo.models import Produto, Promocao
from catalogo.serializers import (
    ProdutoAdminCatalogoSerializer,
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

    def _queryset_admin_catalogo(self):
        """Consulta por página sem uma requisição adicional por produto."""
        hoje = timezone.localdate()
        vigentes = (
            Promocao.objects
            .filter(produto_id=OuterRef('pk'), data_inicio__lte=hoje, data_fim__gte=hoje)
            .order_by('-data_inicio', '-pk')
        )
        return (
            Produto.objects.select_related('categoria')
            .annotate(
                tem_promocao=Exists(vigentes),
                preco_efetivo=Coalesce(
                    Subquery(vigentes.values('preco_promocional')[:1]),
                    F('preco'),
                    output_field=DecimalField(max_digits=7, decimal_places=2),
                ),
                estoque_baixo_calculado=Case(
                    When(estoque__lte=F('estoque_minimo'), then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
        )

    @extend_schema(summary='Listagem administrativa paginada de produtos')
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def admin_catalogo(self, request):
        """A listagem pública permanece isolada do estoque e dados internos."""
        busca = request.query_params.get('busca', '').strip()
        categoria = request.query_params.get('categoria', '').strip()
        situacao = request.query_params.get('situacao', '').strip()

        if len(busca) > 100:
            raise ValidationError({'busca': 'Use até 100 caracteres.'})
        if categoria and (not categoria.isdecimal() or int(categoria) < 1):
            raise ValidationError({'categoria': 'Categoria inválida.'})
        situacoes = {'', 'ativo', 'inativo', 'sem-estoque', 'reposicao'}
        if situacao not in situacoes:
            raise ValidationError({'situacao': 'Situação inválida.'})

        produtos = self._queryset_admin_catalogo()
        if busca:
            produtos = produtos.filter(Q(nome__icontains=busca) | Q(codigo__icontains=busca))
        if categoria:
            produtos = produtos.filter(categoria_id=int(categoria))
        if situacao == 'ativo':
            produtos = produtos.filter(ativo=True)
        elif situacao == 'inativo':
            produtos = produtos.filter(ativo=False)
        elif situacao == 'sem-estoque':
            produtos = produtos.filter(estoque=0)
        elif situacao == 'reposicao':
            produtos = produtos.filter(estoque__lte=F('estoque_minimo'))

        produtos = produtos.order_by('nome', 'pk')
        pagina = self.paginate_queryset(produtos)
        if pagina is not None:
            serializer = ProdutoAdminCatalogoSerializer(
                pagina, many=True, context=self.get_serializer_context(),
            )
            return self.get_paginated_response(serializer.data)
        serializer = ProdutoAdminCatalogoSerializer(
            produtos, many=True, context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @extend_schema(summary='Detalhes internos de um produto para edição administrativa')
    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser])
    def admin_detalhe(self, request, pk=None):
        """Inclui custo e estoque mínimo exclusivamente para operadores autorizados."""
        produto = self.get_object()
        serializer = ProdutoWriteSerializer(produto, context=self.get_serializer_context())
        return Response(serializer.data)

    @extend_schema(summary='Indicadores globais do catálogo administrativo')
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def resumo_admin(self, request):
        hoje = timezone.localdate()
        vigentes = Promocao.objects.filter(
            data_inicio__lte=hoje, data_fim__gte=hoje,
        ).values('produto_id')
        contagens = Produto.objects.aggregate(
            total=Count('pk'),
            ativos=Count('pk', filter=Q(ativo=True)),
            sem_estoque=Count('pk', filter=Q(estoque=0)),
            reposicao=Count('pk', filter=Q(estoque__lte=F('estoque_minimo'))),
            em_promocao=Count('pk', filter=Q(pk__in=vigentes)),
        )
        return Response(contagens)

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
