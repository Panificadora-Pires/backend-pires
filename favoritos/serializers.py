from rest_framework import serializers

from catalogo.models import Produto
from catalogo.serializers import ProdutoListSerializer

from .models import Favorito


class FavoritoSerializer(serializers.ModelSerializer):
    """Favorito do usuário com os dados do produto prontos para o frontend."""

    produto = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.filter(ativo=True),
        write_only=True,
    )
    produto_detalhe = ProdutoListSerializer(
        source='produto',
        read_only=True,
    )

    class Meta:
        model = Favorito
        fields = [
            'id',
            'produto',
            'produto_detalhe',
            'criado_em',
        ]
        read_only_fields = [
            'id',
            'produto_detalhe',
            'criado_em',
        ]

    def validate_produto(self, produto):
        request = self.context.get('request')
        if request and Favorito.objects.filter(
            usuario=request.user,
            produto=produto,
        ).exists():
            raise serializers.ValidationError(
                'Este produto já está nos seus favoritos.'
            )

        return produto
