from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from chatbot.serializers import ChatbotMensagemSerializer
from chatbot.services.provedores import obter_provedor


class ChatbotViewSet(ViewSet):
    """
    Chatbot de ajuda. Responde pelo provedor configurado em `CHATBOT_PROVEDOR` (hoje, regras + FAQ).

    Nada é gravado: o histórico da conversa fica só na sessão do navegador.
    """

    permission_classes = [IsAuthenticated]
    # Só o envio de perguntas tem escopo próprio (definido no @action).
    throttle_scope = None

    @extend_schema(summary='Mensagem de abertura e assuntos sugeridos')
    @action(detail=False, methods=['get'])
    def inicio(self, request):
        resposta = obter_provedor().responder(usuario=request.user, intencao='inicio')
        return Response(resposta.como_dict())

    @extend_schema(summary='Envia uma pergunta ao chatbot', request=ChatbotMensagemSerializer)
    @action(detail=False, methods=['post'], throttle_scope='chatbot')
    def mensagem(self, request):
        serializer = ChatbotMensagemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        resposta = obter_provedor().responder(
            usuario=request.user,
            texto=serializer.validated_data.get('texto'),
            intencao=serializer.validated_data.get('intencao'),
        )
        return Response(resposta.como_dict())
