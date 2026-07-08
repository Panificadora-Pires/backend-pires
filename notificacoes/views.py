from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import Notificacao
from .serializers import NotificacaoSerializer


class NotificacaoViewSet(ReadOnlyModelViewSet):
    """Lista as notificações do usuário logado (RF10 — acompanhamento, ampliado).

    Somente leitura: notificação não é criada nem editada pela API, só pelo
    receiver de `pedido_ficou_pronto`. O único "write" permitido é marcar
    como lida.
    """

    serializer_class = NotificacaoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['lida']

    def get_queryset(self):
        return Notificacao.objects.filter(usuario=self.request.user)

    @action(detail=True, methods=['patch'])
    def marcar_lida(self, request, pk=None):
        notificacao = self.get_object()
        notificacao.lida = True
        notificacao.save(update_fields=['lida'])
        return Response(NotificacaoSerializer(notificacao).data)

    @action(detail=False, methods=['post'])
    def marcar_todas_lidas(self, request):
        self.get_queryset().filter(lida=False).update(lida=True)
        return Response({'detail': 'Todas as notificações foram marcadas como lidas.'})
