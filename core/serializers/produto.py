from rest_framework import serializers

from core.models import Produto


class ProdutoSerializer(serializers.ModelSerializer):
    """Serializer de Produto, expondo o preço com promoção já aplicada (RF09)."""

    preco_atual = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    em_promocao = serializers.SerializerMethodField()

    class Meta:
        model = Produto
        fields = [
            'id',
            'nome',
            'descricao',
            'preco',
            'preco_atual',
            'em_promocao',
            'estoque',
            'categoria',
            'ativo',
        ]

    def get_em_promocao(self, obj):
        return obj.promocao_ativa is not None
