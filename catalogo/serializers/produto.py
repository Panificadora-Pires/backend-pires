from rest_framework import serializers

from catalogo.models import Produto


class ProdutoListSerializer(serializers.ModelSerializer):
    """Cardápio (RF09): só os dados que o aluno precisa ver. Sem preço de custo."""

    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True)
    preco_atual = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)
    em_promocao = serializers.SerializerMethodField()

    class Meta:
        model = Produto
        fields = [
            'id',
            'codigo',
            'nome',
            'slug',
            'imagem',
            'categoria',
            'categoria_nome',
            'unidade_medida',
            'preco',
            'preco_atual',
            'em_promocao',
            'destaque',
        ]

    def get_em_promocao(self, obj):
        return obj.promocao_ativa is not None


class ProdutoDetailSerializer(ProdutoListSerializer):
    """Cardápio detalhado (tela do produto): acrescenta descrição, estoque e status."""

    class Meta(ProdutoListSerializer.Meta):
        fields = ProdutoListSerializer.Meta.fields + ['descricao', 'estoque', 'ativo']


class ProdutoWriteSerializer(serializers.ModelSerializer):
    """Cadastro/edição pela administração (RF02). Inclui dados internos do negócio."""

    class Meta:
        model = Produto
        fields = [
            'id',
            'codigo',
            'nome',
            'slug',
            'descricao',
            'categoria',
            'imagem',
            'unidade_medida',
            'preco',
            'preco_custo',
            'estoque',
            'estoque_minimo',
            'destaque',
            'ativo',
        ]
        read_only_fields = ['codigo', 'slug']
