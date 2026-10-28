from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from chat.serializers import ChatPedidoSerializer, MensagemSerializer, MensagemWriteSerializer
from chat.services.chat import ChatEncerradoError, contar_nao_lidas, enviar_mensagem, marcar_lidas
from core.permissions import IsOwnerOrAdmin
from pedidos.models import Pedido


class ChatPedidoViewSet(GenericViewSet):
    """
    Chat de um pedido entre o cliente dono do pedido e a administração.

    O `pk` da rota é o id do pedido. O cliente só enxerga os próprios pedidos (os
    demais respondem 404); o administrador enxerga todos.
    """

    serializer_class = ChatPedidoSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = None
    filter_backends = []
    # Só o envio de mensagens tem escopo próprio (definido no @action); sem escopo, não há limite extra.
    throttle_scope = None

    def get_queryset(self):
        pedidos = Pedido.objects.select_related('usuario')

        if self.request.user.is_staff:
            return pedidos

        return pedidos.filter(usuario=self.request.user)

    @extend_schema(summary='Mensagens e situação do chat do pedido')
    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(summary='Envia uma mensagem no chat do pedido', request=MensagemWriteSerializer)
    @action(detail=True, methods=['post'], throttle_scope='chat_mensagem')
    def mensagens(self, request, pk=None):
        pedido = self.get_object()
        serializer = MensagemWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            mensagem = enviar_mensagem(pedido, request.user, serializer.validated_data['texto'])
        except ChatEncerradoError as erro:
            return Response({'detail': str(erro)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            MensagemSerializer(mensagem, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(summary='Marca como lidas as mensagens do outro lado da conversa', request=None)
    @action(detail=True, methods=['post'])
    def marcar_lidas(self, request, pk=None):
        return Response({'marcadas': marcar_lidas(self.get_object(), request.user)})

    @extend_schema(summary='Contagem de mensagens não lidas por pedido')
    @action(detail=False, methods=['get'])
    def nao_lidas(self, request):
        return Response(contar_nao_lidas(request.user))
