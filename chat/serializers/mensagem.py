import unicodedata

from django.conf import settings
from rest_framework import serializers

from chat.models import Mensagem


def limpar_texto(texto):
    """Mantém quebras de linha e remove os demais caracteres de controle."""

    texto = texto.replace('\r\n', '\n').replace('\r', '\n')
    return ''.join(
        caractere for caractere in texto if caractere == '\n' or unicodedata.category(caractere) != 'Cc'
    ).strip()


class MensagemSerializer(serializers.ModelSerializer):
    """Leitura. Não expõe o autor: o cliente só precisa saber se a mensagem veio da padaria."""

    minha = serializers.SerializerMethodField()

    class Meta:
        model = Mensagem
        fields = ['id', 'texto', 'enviada_pela_padaria', 'minha', 'criada_em', 'lida_em']
        read_only_fields = fields

    def get_minha(self, mensagem):
        request = self.context.get('request')
        return bool(request and mensagem.autor_id == request.user.id)


class MensagemWriteSerializer(serializers.Serializer):
    """Envio. Autor, lado da conversa e datas vêm do servidor."""

    texto = serializers.CharField()

    def validate_texto(self, texto):
        texto = limpar_texto(texto)

        if not texto:
            raise serializers.ValidationError('Escreva uma mensagem.')

        limite = settings.CHAT_MENSAGEM_TAMANHO_MAXIMO
        if len(texto) > limite:
            raise serializers.ValidationError(f'A mensagem pode ter no máximo {limite} caracteres.')

        return texto
