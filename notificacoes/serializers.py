from rest_framework import serializers

from .models import Notificacao


class NotificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacao
        fields = ['id', 'pedido', 'mensagem', 'lida', 'criada_em']
        read_only_fields = ['pedido', 'mensagem', 'criada_em']
