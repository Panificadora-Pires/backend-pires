from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from catalogo.models import Produto
from pedidos.models import ItemPedido, Pedido
from pedidos.signals import pedido_ficou_pronto


class ItemPedidoSerializer(serializers.ModelSerializer):
    """Representa um item já salvo dentro de um pedido (leitura)."""

    produto_nome = serializers.CharField(source='produto.nome', read_only=True)
    subtotal = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = ItemPedido
        fields = ['id', 'produto', 'produto_nome', 'quantidade', 'preco_unitario', 'subtotal']
        read_only_fields = ['preco_unitario']


class ItemPedidoCreateSerializer(serializers.Serializer):
    """Usado apenas na criação do pedido: produto + quantidade desejada (RF04)."""

    produto = serializers.PrimaryKeyRelatedField(queryset=Produto.objects.filter(ativo=True))
    quantidade = serializers.IntegerField(min_value=1)


class PedidoSerializer(serializers.ModelSerializer):
    """Serializer principal de Pedido: leitura aninhada + criação com itens (RF04, RF08)."""

    itens = ItemPedidoSerializer(many=True, read_only=True)
    itens_criacao = ItemPedidoCreateSerializer(many=True, write_only=True)
    usuario_nome = serializers.CharField(source='usuario.name', read_only=True)
    total = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

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
        read_only_fields = ['usuario', 'status', 'data', 'codigo_retirada']

    def validate_itens_criacao(self, itens):
        if not itens:
            raise serializers.ValidationError('O pedido precisa ter ao menos um item.')

        # RN03 — não é permitido reservar produto sem estoque
        for item in itens:
            produto = item['produto']
            if produto.estoque < item['quantidade']:
                raise serializers.ValidationError(
                    f'Estoque insuficiente para "{produto.nome}" (disponível: {produto.estoque}).'
                )
        return itens

    @transaction.atomic
    def create(self, validated_data):
        itens_data = validated_data.pop('itens_criacao')
        usuario = self.context['request'].user

        pedido = Pedido.objects.create(usuario=usuario)

        for item in itens_data:
            produto = item['produto']
            quantidade = item['quantidade']

            # RN02 — baixa automática de estoque ao criar/confirmar o pedido
            produto.estoque -= quantidade
            produto.save(update_fields=['estoque'])

            ItemPedido.objects.create(
                pedido=pedido,
                produto=produto,
                quantidade=quantidade,
                preco_unitario=produto.preco_atual,
            )

        return pedido


class PedidoStatusUpdateSerializer(serializers.ModelSerializer):
    """Usado exclusivamente pela administração para avançar o status (RF07, RN04, RN07)."""

    class Meta:
        model = Pedido
        fields = ['status']

    def validate_status(self, novo_status):
        if not self.instance.pode_transicionar_para(novo_status):
            raise serializers.ValidationError(
                f'Não é possível mudar de "{self.instance.get_status_display()}" '
                f'para "{dict(Pedido.Status.choices).get(novo_status, novo_status)}".'
            )
        return novo_status

    def save(self, **kwargs):
        status_anterior = self.instance.status
        self.instance.status_atualizado_em = timezone.now()
        pedido = super().save(**kwargs)

        # Dispara o signal só na transição pendente/confirmado -> pronto,
        # nunca de novo se o status já era "pronto" (evita notificação duplicada).
        if status_anterior != Pedido.Status.PRONTO and pedido.status == Pedido.Status.PRONTO:
            pedido_ficou_pronto.send(sender=Pedido, pedido=pedido)

        return pedido


class RetiradaPorQRCodeSerializer(serializers.Serializer):
    """Usado pela administração no balcão, ao ler o QR Code do aluno."""

    codigo_retirada = serializers.UUIDField()

    def validate_codigo_retirada(self, codigo_retirada):
        try:
            pedido = Pedido.objects.get(codigo_retirada=codigo_retirada)
        except Pedido.DoesNotExist as exc:
            raise serializers.ValidationError('Código de retirada inválido.') from exc

        if not pedido.pode_transicionar_para(Pedido.Status.RETIRADO):
            raise serializers.ValidationError(
                f'Este pedido está com status "{pedido.get_status_display()}" e não pode ser retirado agora.'
            )

        self.pedido = pedido
        return codigo_retirada

    def save(self, **kwargs):
        self.pedido.status = Pedido.Status.RETIRADO
        self.pedido.status_atualizado_em = timezone.now()
        self.pedido.save(update_fields=['status', 'status_atualizado_em'])
        return self.pedido
