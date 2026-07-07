from rest_framework import serializers

from core.models import Promocao


class PromocaoSerializer(serializers.ModelSerializer):
    """Serializer de Promoção. Validações replicam o Model.clean() (RN05)."""

    produto_nome = serializers.CharField(source='produto.nome', read_only=True)

    class Meta:
        model = Promocao
        fields = ['id', 'produto', 'produto_nome', 'preco_promocional', 'data_inicio', 'data_fim']

    def validate(self, attrs):
        produto = attrs.get('produto') or getattr(self.instance, 'produto', None)
        preco_promocional = attrs.get('preco_promocional', getattr(self.instance, 'preco_promocional', None))
        data_inicio = attrs.get('data_inicio', getattr(self.instance, 'data_inicio', None))
        data_fim = attrs.get('data_fim', getattr(self.instance, 'data_fim', None))

        if data_inicio and data_fim and data_fim < data_inicio:
            raise serializers.ValidationError('A data de fim não pode ser anterior à data de início.')
        if produto and preco_promocional is not None and preco_promocional >= produto.preco:
            raise serializers.ValidationError(
                'O preço promocional deve ser menor que o preço original do produto.'
            )
        return attrs
