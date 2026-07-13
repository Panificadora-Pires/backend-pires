from rest_framework.viewsets import ModelViewSet

from catalogo.models import Categoria
from core.permissions import IsAdminOrReadOnly
from catalogo.serializers import CategoriaSerializer


class CategoriaViewSet(ModelViewSet):
    """CRUD de categorias, gerenciável pela administração sem precisar mexer em código."""

    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['ativa']
