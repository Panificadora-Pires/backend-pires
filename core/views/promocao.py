from rest_framework.viewsets import ModelViewSet

from core.models import Promocao
from core.permissions import IsAdminOrReadOnly
from core.serializers import PromocaoSerializer


class PromocaoViewSet(ModelViewSet):
    """RF03 — Cadastro de promoção (RN05 — somente administração cadastra)."""

    queryset = Promocao.objects.all().order_by('-data_inicio')
    serializer_class = PromocaoSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['produto']
