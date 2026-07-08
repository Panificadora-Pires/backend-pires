from rest_framework.viewsets import ModelViewSet

from catalogo.models import Produto
from catalogo.serializers import ProdutoDetailSerializer, ProdutoListSerializer, ProdutoWriteSerializer
from core.permissions import IsAdminOrReadOnly


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
