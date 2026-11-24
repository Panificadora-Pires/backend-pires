from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from catalogo.models import Categoria
from catalogo.search import buscar_sem_acentos
from catalogo.serializers import CategoriaSerializer
from core.permissions import IsAdminOrReadOnly


class CategoriaViewSet(ModelViewSet):
    """CRUD de categorias, gerenciável pela administração sem precisar mexer em código."""

    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['ativa']

    @extend_schema(summary='Categorias administrativas com paginação e filtros')
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def admin_listagem(self, request):
        busca = (request.query_params.get('busca') or '').strip()
        situacao = (request.query_params.get('situacao') or '').strip()
        if len(busca) > 100:
            raise ValidationError({'busca': 'Use no máximo 100 caracteres.'})
        if situacao not in ('', 'ativa', 'inativa'):
            raise ValidationError({'situacao': 'Situação inválida.'})

        categorias = Categoria.objects.all()
        if busca:
            expressao = buscar_sem_acentos(busca)
            categorias = categorias.filter(
                Q(nome__iregex=expressao)
                | Q(descricao__iregex=expressao)
                | Q(slug__iregex=expressao)
            )
        if situacao:
            categorias = categorias.filter(ativa=(situacao == 'ativa'))
        categorias = categorias.order_by('ordem', 'nome', 'pk')

        pagina = self.paginate_queryset(categorias)
        if pagina is not None:
            return self.get_paginated_response(
                self.get_serializer(pagina, many=True).data
            )
        return Response(self.get_serializer(categorias, many=True).data)

    @extend_schema(summary='Indicadores globais de categorias administrativas')
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def resumo_admin(self, request):
        return Response(Categoria.objects.aggregate(
            total=Count('pk'),
            ativas=Count('pk', filter=Q(ativa=True)),
            inativas=Count('pk', filter=Q(ativa=False)),
        ))
