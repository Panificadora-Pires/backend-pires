from rest_framework import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from .models import Favorito
from .serializers import FavoritoSerializer


class FavoritoViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    """
    Favoritos do usuário autenticado.

    GET /favoritos/                  -> lista os favoritos
    POST /favoritos/                 -> adiciona um produto
    DELETE /favoritos/{produto_id}/  -> remove pelo id do produto
    """

    serializer_class = FavoritoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'produto_id'

    def get_queryset(self):
        return (
            Favorito.objects
            .filter(usuario=self.request.user)
            .select_related('produto__categoria')
            .order_by('-criado_em')
        )

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)
