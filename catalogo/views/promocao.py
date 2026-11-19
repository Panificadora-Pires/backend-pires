from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
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

    @extend_schema(summary='Resumo administrativo agregado de promoções')
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def resumo_admin(self, request):
        """Contagens globais, sem baixar todas as ofertas para o Dashboard."""
        hoje = timezone.localdate()
        return Response(Promocao.objects.aggregate(
            total=Count('pk'),
            ativas=Count('pk', filter=Q(data_inicio__lte=hoje, data_fim__gte=hoje)),
        ))
