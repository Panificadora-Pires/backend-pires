from rest_framework.viewsets import ModelViewSet

from core.models import Categoria
from core.permissions import IsAdminOrReadOnly
from core.serializers import CategoriaSerializer


class CategoriaViewSet(ModelViewSet):
    """CRUD de categorias, gerenciável pela administração sem precisar mexer em código."""

    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['ativa']
