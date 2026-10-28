from rest_framework import serializers

from chat.services.chat import (
    chat_somente_leitura,
    mensagens_do_pedido,
    mensagens_nao_lidas,
    prazo_do_chat,
)

from .mensagem import MensagemSerializer

# Limite de mensagens devolvidas por consulta (as mais recentes).
MAXIMO_MENSAGENS_EXIBIDAS = 200


class ChatPedidoSerializer(serializers.Serializer):
    """Chat de um pedido (a instância é o próprio Pedido)."""

    pedido = serializers.IntegerField(source='id', read_only=True)
    status_pedido = serializers.CharField(source='status', read_only=True)
    somente_leitura = serializers.SerializerMethodField()
    encerra_em = serializers.SerializerMethodField()
    nao_lidas = serializers.SerializerMethodField()
    mensagens = serializers.SerializerMethodField()

    def get_somente_leitura(self, pedido):
        return chat_somente_leitura(pedido)

    def get_encerra_em(self, pedido):
        encerra_em = prazo_do_chat(pedido)
        return serializers.DateTimeField().to_representation(encerra_em) if encerra_em else None

    def get_nao_lidas(self, pedido):
        return mensagens_nao_lidas(self.context['request'].user).filter(conversa__pedido=pedido).count()

    def get_mensagens(self, pedido):
        recentes = list(mensagens_do_pedido(pedido).order_by('-criada_em', '-id')[:MAXIMO_MENSAGENS_EXIBIDAS])
        recentes.reverse()
        return MensagemSerializer(recentes, many=True, context=self.context).data
