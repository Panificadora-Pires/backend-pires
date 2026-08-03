from rest_framework.viewsets import ModelViewSet

from catalogo.models import Promocao
from catalogo.serializers import PromocaoSerializer
from core.permissions import IsAdminOrReadOnly


class PromocaoViewSet(ModelViewSet):
    """RF03 — Cadastro de promoção (RN05 — somente administração cadastra)."""

    queryset = Promocao.objects.all().order_by('-data_inicio')
    serializer_class = PromocaoSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['produto']
