from rest_framework import serializers

from catalogo.models import Categoria


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nome', 'slug', 'descricao', 'ordem', 'ativa']
        read_only_fields = ['slug']
