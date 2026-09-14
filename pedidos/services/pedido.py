"""Operações transacionais de criação e cancelamento de pedidos."""

from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from catalogo.models import Produto
from pedidos.models import ItemPedido, Pedido


@transaction.atomic
def criar_pedido_reservando_estoque(*, usuario, itens_data, **pedido_kwargs):
    """Cria pedido, congela os preços e reserva estoque sob lock de banco."""

    ids_produtos = [item['produto'].pk for item in itens_data]

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
        produto = produtos_bloqueados.get(produto_original.pk)

        if produto is None:
            raise serializers.ValidationError(
                {
                    'itens_criacao': (
                        f'O produto "{produto_original.nome}" '
                        'não está mais disponível.'
                    )
                }
            )

        if produto.estoque < quantidade:
            raise serializers.ValidationError(
                {
                    'itens_criacao': (
                        f'Estoque insuficiente para "{produto.nome}" '
                        f'(disponível: {produto.estoque}).'
                    )
                }
            )

    pedido = Pedido.objects.create(
        usuario=usuario,
        **pedido_kwargs,
    )

    itens_para_criar = []
    produtos_para_atualizar = []

    for item in itens_data:
        produto = produtos_bloqueados[item['produto'].pk]
        quantidade = item['quantidade']

        produto.estoque -= quantidade
        produtos_para_atualizar.append(produto)

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
    ItemPedido.objects.bulk_create(itens_para_criar)

    return pedido


@transaction.atomic
def devolver_estoque_pedido(pedido):
    """Devolve o estoque exatamente uma vez, mesmo com chamadas repetidas."""

    pedido_bloqueado = (
        Pedido.objects
        .select_for_update()
        .get(pk=pedido.pk)
    )

    if pedido_bloqueado.estoque_devolvido:
        pedido.estoque_devolvido = True
        return False

    itens = list(pedido_bloqueado.itens.all())

    for item in itens:
        Produto.objects.filter(pk=item.produto_id).update(
            estoque=F('estoque') + item.quantidade,
        )

    pedido_bloqueado.estoque_devolvido = True
    pedido_bloqueado.save(update_fields=['estoque_devolvido'])
    pedido.estoque_devolvido = True

    return True
