from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from catalogo.models import Produto
from pedidos.models import ItemPedido, Pedido
from pedidos.signals import pedido_ficou_pronto


class ItemPedidoSerializer(serializers.ModelSerializer):
    """Representação de um item salvo no pedido."""

    produto_nome = serializers.CharField(
        source='produto.nome',
        read_only=True,
    )

    subtotal = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = ItemPedido
        fields = [
            'id',
            'produto',
            'produto_nome',
            'quantidade',
            'preco_unitario',
            'subtotal',
        ]
        read_only_fields = [
            'id',
            'produto',
            'produto_nome',
            'quantidade',
            'preco_unitario',
            'subtotal',
        ]


class ItemPedidoCreateSerializer(serializers.Serializer):
    """Item recebido durante a criação de um pedido."""

    produto = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.filter(
            ativo=True,
        )
    )

    quantidade = serializers.IntegerField(
        min_value=1,
    )


class PedidoSerializer(serializers.ModelSerializer):
    """Leitura e criação de pedidos."""

    itens = ItemPedidoSerializer(
        many=True,
        read_only=True,
    )

    itens_criacao = ItemPedidoCreateSerializer(
        many=True,
        write_only=True,
    )

    usuario_nome = serializers.CharField(
        source='usuario.name',
        read_only=True,
    )

    total = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        read_only=True,
    )

    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
    )

    class Meta:
        model = Pedido
        fields = [
            'id',
            'usuario',
            'usuario_nome',
            'data',
            'status',
            'status_display',
            'itens',
            'itens_criacao',
            'total',
            'codigo_retirada',
        ]
        read_only_fields = [
            'id',
            'usuario',
            'usuario_nome',
            'data',
            'status',
            'status_display',
            'itens',
            'total',
            'codigo_retirada',
        ]

    def validate_itens_criacao(self, itens):
        if not itens:
            raise serializers.ValidationError(
                'O pedido precisa ter ao menos um item.'
            )

        produtos_encontrados = set()

        for item in itens:
            produto = item['produto']
            quantidade = item['quantidade']

            if produto.pk in produtos_encontrados:
                raise serializers.ValidationError(
                    (
                        f'O produto "{produto.nome}" foi informado '
                        'mais de uma vez no mesmo pedido.'
                    )
                )

            produtos_encontrados.add(
                produto.pk,
            )

            if produto.estoque < quantidade:
                raise serializers.ValidationError(
                    (
                        f'Estoque insuficiente para '
                        f'"{produto.nome}" '
                        f'(disponível: {produto.estoque}).'
                    )
                )

        return itens

    @transaction.atomic
    def create(self, validated_data):
        itens_data = validated_data.pop(
            'itens_criacao',
        )

        usuario = self.context['request'].user

        ids_produtos = [
            item['produto'].pk
            for item in itens_data
        ]

        produtos_bloqueados = (
            Produto.objects
            .select_for_update()
            .filter(
                pk__in=ids_produtos,
                ativo=True,
            )
            .in_bulk()
        )

        for item in itens_data:
            produto_original = item['produto']
            quantidade = item['quantidade']

            produto = produtos_bloqueados.get(
                produto_original.pk,
            )

            if produto is None:
                raise serializers.ValidationError(
                    {
                        'itens_criacao': (
                            f'O produto '
                            f'"{produto_original.nome}" '
                            'não está mais disponível.'
                        )
                    }
                )

            if produto.estoque < quantidade:
                raise serializers.ValidationError(
                    {
                        'itens_criacao': (
                            f'Estoque insuficiente para '
                            f'"{produto.nome}" '
                            f'(disponível: {produto.estoque}).'
                        )
                    }
                )

        pedido = Pedido.objects.create(
            usuario=usuario,
        )

        itens_para_criar = []
        produtos_para_atualizar = []

        for item in itens_data:
            produto = produtos_bloqueados[
                item['produto'].pk
            ]
            quantidade = item['quantidade']

            produto.estoque -= quantidade

            produtos_para_atualizar.append(
                produto,
            )

            itens_para_criar.append(
                ItemPedido(
                    pedido=pedido,
                    produto=produto,
                    quantidade=quantidade,
                    preco_unitario=produto.preco_atual,
                )
            )

        Produto.objects.bulk_update(
            produtos_para_atualizar,
            ['estoque'],
        )

        ItemPedido.objects.bulk_create(
            itens_para_criar,
        )

        return pedido


class PedidoStatusUpdateSerializer(
    serializers.ModelSerializer
):
    """Alteração administrativa do status do pedido."""

    class Meta:
        model = Pedido
        fields = [
            'status',
        ]

    def validate_status(self, novo_status):
        if not self.instance.pode_transicionar_para(
            novo_status,
        ):
            nome_status = dict(
                Pedido.Status.choices
            ).get(
                novo_status,
                novo_status,
            )

            raise serializers.ValidationError(
                (
                    'Não é possível mudar de '
                    f'"{self.instance.get_status_display()}" '
                    f'para "{nome_status}".'
                )
            )

        return novo_status

    def update(self, instance, validated_data):
        status_anterior = instance.status

        instance.status = validated_data['status']
        instance.status_atualizado_em = timezone.now()

        instance.save(
            update_fields=[
                'status',
                'status_atualizado_em',
            ]
        )

        if (
            status_anterior != Pedido.Status.PRONTO
            and instance.status == Pedido.Status.PRONTO
        ):
            pedido_ficou_pronto.send(
                sender=Pedido,
                pedido=instance,
            )

        return instance


class RetiradaPorQRCodeSerializer(
    serializers.Serializer
):
    """Confirmação de retirada usando o QR Code."""

    codigo_retirada = serializers.UUIDField()

    def validate_codigo_retirada(
        self,
        codigo_retirada,
    ):
        try:
            pedido = Pedido.objects.only(
                'id',
                'status',
            ).get(
                codigo_retirada=codigo_retirada,
            )
        except Pedido.DoesNotExist as exc:
            raise serializers.ValidationError(
                'Código de retirada inválido.'
            ) from exc

        if not pedido.pode_transicionar_para(
            Pedido.Status.RETIRADO,
        ):
            raise serializers.ValidationError(
                (
                    'Este pedido está com status '
                    f'"{pedido.get_status_display()}" '
                    'e não pode ser retirado agora.'
                )
            )

        self.pedido_id = pedido.pk

        return codigo_retirada

    @transaction.atomic
    def save(self, **kwargs):
        pedido = (
            Pedido.objects
            .select_for_update()
            .get(pk=self.pedido_id)
        )

        if not pedido.pode_transicionar_para(
            Pedido.Status.RETIRADO,
        ):
            raise serializers.ValidationError(
                {
                    'codigo_retirada': (
                        'O pedido não pode mais ser retirado '
                        'no status atual.'
                    )
                }
            )

        pedido.status = Pedido.Status.RETIRADO
        pedido.status_atualizado_em = timezone.now()

        pedido.save(
            update_fields=[
                'status',
                'status_atualizado_em',
            ]
        )

        return pedido
