from rest_framework import serializers

TAMANHO_MAXIMO_PERGUNTA = 300


class ChatbotMensagemSerializer(serializers.Serializer):
    """Pergunta ao chatbot: texto livre ou a intenção de um botão."""

    texto = serializers.CharField(required=False, allow_blank=True, max_length=TAMANHO_MAXIMO_PERGUNTA)
    intencao = serializers.SlugField(required=False, max_length=50)

    def validate(self, attrs):
        if not attrs.get('texto') and not attrs.get('intencao'):
            raise serializers.ValidationError('Escreva uma pergunta ou escolha um assunto.')
        return attrs
