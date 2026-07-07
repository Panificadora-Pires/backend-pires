from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import Pedido
from core.permissions import IsOwnerOrAdmin
from core.serializers import PedidoSerializer, PedidoStatusUpdateSerializer


class PedidoViewSet(ModelViewSet):
    """RF04 — criação de pedido / RF07 — gestão de status / RF10 — acompanhamento."""

    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    filterset_fields = ['status']

    def get_queryset(self):
        """Aluno só vê os próprios pedidos; administração vê todos (RF10)."""
        usuario = self.request.user
        queryset = Pedido.objects.all().prefetch_related('itens__produto').order_by('-data')
        if usuario.is_staff:
            return queryset
        return queryset.filter(usuario=usuario)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @extend_schema(
        summary='Alterar status do pedido',
        description='Avança o status do pedido seguindo a RN04. Apenas a administração pode chamar.',
        request=PedidoStatusUpdateSerializer,
        responses={200: PedidoSerializer, 400: None, 403: None},
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def alterar_status(self, request, pk=None):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Apenas a administração pode alterar o status do pedido.'},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        pedido = self.get_object()
        serializer = PedidoStatusUpdateSerializer(pedido, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(PedidoSerializer(pedido).data, status=http_status.HTTP_200_OK)
