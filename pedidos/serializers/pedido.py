from django.utils import timezone
from rest_framework import serializers

from catalogo.models import Produto
from pedidos.models import ItemPedido, Pedido
from pedidos.services.pagamentos import MercadoPagoError, preparar_cancelamento_financeiro
from pedidos.services.pedido import (
    criar_pedido_reservando_estoque,
    devolver_estoque_pedido,
)
from pedidos.signals import pedido_ficou_pronto


class ItemPedidoSerializer(serializers.ModelSerializer):
    """Representação de um item salvo no pedido."""

    produto_nome = serializers.CharField(source='produto.nome', read_only=True)
    subtotal = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

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
        read_only_fields = fields


class ItemPedidoCreateSerializer(serializers.Serializer):
    """Item recebido durante a criação de um pedido."""

    produto = serializers.PrimaryKeyRelatedField(
        queryset=Produto.objects.filter(ativo=True),
    )
    quantidade = serializers.IntegerField(min_value=1)


def validar_itens_criacao(itens):
    if not itens:
        raise serializers.ValidationError('O pedido precisa ter ao menos um item.')

    produtos_encontrados = set()
    for item in itens:
        produto = item['produto']
        quantidade = item['quantidade']

        if produto.pk in produtos_encontrados:
            raise serializers.ValidationError(
                f'O produto "{produto.nome}" foi informado mais de uma vez no mesmo pedido.'
            )
        produtos_encontrados.add(produto.pk)

        if produto.estoque < quantidade:
            raise serializers.ValidationError(
                f'Estoque insuficiente para "{produto.nome}" (disponível: {produto.estoque}).'
            )

    return itens


class PedidoSerializer(serializers.ModelSerializer):
    """Leitura e criação tradicional de pedidos."""

    itens = ItemPedidoSerializer(many=True, read_only=True)
    itens_criacao = ItemPedidoCreateSerializer(many=True, write_only=True)
    usuario_nome = serializers.CharField(source='usuario.name', read_only=True)
    total = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    forma_pagamento_display = serializers.CharField(
        source='get_forma_pagamento_display',
        read_only=True,
    )
    status_pagamento_display = serializers.CharField(
        source='get_status_pagamento_display',
        read_only=True,
    )

    class Meta:
        model = Pedido
        fields = [
            'id',
            'usuario',
            'usuario_nome',
            'data',
            'status_atualizado_em',
            'status',
            'status_display',
            'itens',
            'itens_criacao',
            'total',
            'codigo_retirada',
            'forma_pagamento',
            'forma_pagamento_display',
            'status_pagamento',
            'status_pagamento_display',
            'pagamento_expira_em',
        ]
        read_only_fields = [
            'id',
            'usuario',
            'usuario_nome',
            'data',
            'status_atualizado_em',
            'status',
            'status_display',
            'itens',
            'total',
            'codigo_retirada',
            'forma_pagamento',
            'forma_pagamento_display',
            'status_pagamento',
            'status_pagamento_display',
            'pagamento_expira_em',
        ]

    def validate_itens_criacao(self, itens):
        return validar_itens_criacao(itens)

    def create(self, validated_data):
        itens_data = validated_data.pop('itens_criacao')
        return criar_pedido_reservando_estoque(
            usuario=self.context['request'].user,
            itens_data=itens_data,
            forma_pagamento=Pedido.FormaPagamento.DINHEIRO,
            status_pagamento=Pedido.StatusPagamento.PENDENTE,
        )


class CheckoutBaseSerializer(serializers.Serializer):
    checkout_id = serializers.UUIDField()
    itens_criacao = ItemPedidoCreateSerializer(many=True)

    def validate_itens_criacao(self, itens):
        return validar_itens_criacao(itens)


class CheckoutDinheiroSerializer(CheckoutBaseSerializer):
    """Checkout que será pago presencialmente na retirada."""


class CheckoutMercadoPagoSerializer(CheckoutBaseSerializer):
    """Dados enviados pelo Payment Brick junto com os itens do carrinho."""

    payment_type = serializers.CharField(max_length=40, allow_blank=True)
    form_data = serializers.JSONField()

    def validate_form_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Dados do pagamento inválidos.')
        if not value.get('payment_method_id'):
            raise serializers.ValidationError('Meio de pagamento não informado.')
        return value


class PagamentoPedidoSerializer(serializers.ModelSerializer):
    forma_pagamento_display = serializers.CharField(
        source='get_forma_pagamento_display',
        read_only=True,
    )
    status_pagamento_display = serializers.CharField(
        source='get_status_pagamento_display',
        read_only=True,
    )

    class Meta:
        model = Pedido
        fields = [
            'id',
            'forma_pagamento',
            'forma_pagamento_display',
            'status_pagamento',
            'status_pagamento_display',
            'mercadopago_payment_id',
            'mercadopago_status',
            'mercadopago_status_detail',
            'pagamento_expira_em',
            'pix_qr_code',
            'pix_qr_code_base64',
        ]
        read_only_fields = fields


class PedidoStatusUpdateSerializer(serializers.ModelSerializer):
    """Alteração administrativa do status do pedido."""

    class Meta:
        model = Pedido
        fields = ['status']

    def validate_status(self, novo_status):
        if not self.instance.pode_transicionar_para(novo_status):
            nome_status = dict(Pedido.Status.choices).get(novo_status, novo_status)
            raise serializers.ValidationError(
                f'Não é possível mudar de "{self.instance.get_status_display()}" para "{nome_status}".'
            )

        if (
            novo_status == Pedido.Status.CONFIRMADO
            and self.instance.forma_pagamento in {
                Pedido.FormaPagamento.PIX,
                Pedido.FormaPagamento.CARTAO,
            }
            and self.instance.status_pagamento != Pedido.StatusPagamento.APROVADO
        ):
            raise serializers.ValidationError(
                'O pedido online só pode ser confirmado após a aprovação do pagamento.'
            )

        return novo_status

    def update(self, instance, validated_data):
        status_anterior = instance.status
        novo_status = validated_data['status']

        if novo_status == Pedido.Status.CANCELADO:
            try:
                instance = preparar_cancelamento_financeiro(instance)
            except MercadoPagoError as exc:
                raise serializers.ValidationError(
                    f'Não foi possível cancelar o pedido porque o pagamento não pôde ser conciliado ({exc}).'
                ) from exc

        instance.status = novo_status
        instance.status_atualizado_em = timezone.now()

        campos = ['status', 'status_atualizado_em']
        if instance.status_pagamento == Pedido.StatusPagamento.REEMBOLSADO:
            campos.append('status_pagamento')

        if (
            instance.status == Pedido.Status.RETIRADO
            and instance.forma_pagamento == Pedido.FormaPagamento.DINHEIRO
        ):
            instance.status_pagamento = Pedido.StatusPagamento.APROVADO
            campos.append('status_pagamento')

        instance.save(update_fields=campos)

        if instance.status == Pedido.Status.CANCELADO:
            devolver_estoque_pedido(instance)

        if (
            status_anterior != Pedido.Status.PRONTO
            and instance.status == Pedido.Status.PRONTO
        ):
            pedido_ficou_pronto.send(sender=Pedido, pedido=instance)

        return instance


class RetiradaPorQRCodeSerializer(serializers.Serializer):
    """Confirmação de retirada usando o QR Code."""

    codigo_retirada = serializers.UUIDField()

    def validate_codigo_retirada(self, codigo_retirada):
        try:
            pedido = Pedido.objects.only(
                'id',
                'status',
                'forma_pagamento',
                'status_pagamento',
            ).get(codigo_retirada=codigo_retirada)
        except Pedido.DoesNotExist as exc:
            raise serializers.ValidationError('Código de retirada inválido.') from exc

        if not pedido.pode_transicionar_para(Pedido.Status.RETIRADO):
            raise serializers.ValidationError(
                f'Este pedido está com status "{pedido.get_status_display()}" e não pode ser retirado agora.'
            )

        self.pedido_id = pedido.pk
        return codigo_retirada

    def save(self, **kwargs):
        from django.db import transaction

        with transaction.atomic():
            pedido = Pedido.objects.select_for_update().get(pk=self.pedido_id)

            if not pedido.pode_transicionar_para(Pedido.Status.RETIRADO):
                raise serializers.ValidationError(
                    {'codigo_retirada': 'O pedido não pode mais ser retirado no status atual.'}
                )

            pedido.status = Pedido.Status.RETIRADO
            pedido.status_atualizado_em = timezone.now()
            campos = ['status', 'status_atualizado_em']

            if pedido.forma_pagamento == Pedido.FormaPagamento.DINHEIRO:
                pedido.status_pagamento = Pedido.StatusPagamento.APROVADO
                campos.append('status_pagamento')

            pedido.save(update_fields=campos)

        return pedido
