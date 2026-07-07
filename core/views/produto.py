from rest_framework.viewsets import ModelViewSet

from core.models import Produto
from core.permissions import IsAdminOrReadOnly
from core.serializers import ProdutoSerializer


class ProdutoViewSet(ModelViewSet):
    """RF02 — Cadastro de produto / RF09 — Consulta de cardápio do dia."""

    queryset = Produto.objects.all().order_by('nome')
    serializer_class = ProdutoSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['categoria', 'ativo']
