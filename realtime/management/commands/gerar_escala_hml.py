"""Gera ou remove dados sintéticos de escala na HML (QA da issue frontend #56, PR7B).

Somente a branch `deploy/pr6-hml-asgi` contém este comando. Recusa host ou banco fora
da HML Neon e exige `--confirmar-hml`. Nenhum dado real é lido ou alterado: tudo o que
é criado fica marcado (e-mails `@escala.hml.invalid`, nomes com prefixo `Escala ` e
códigos `ESC`) e só isso é removido por `--remover`.

Uso no console do Fabroku (HML):
    python manage.py gerar_escala_hml --confirmar-hml
    python manage.py gerar_escala_hml --confirmar-hml --produtos 100 --pedidos 100
    python manage.py gerar_escala_hml --confirmar-hml --remover

Usa bulk_create: não dispara signals (sem notificações, e-mails ou eventos realtime).
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from catalogo.models import Categoria, Produto, Promocao
from pedidos.models import ItemPedido, Pedido

HOST_HML = 'backend-pires-hml.class.fabricadesoftware.ifc.edu.br'
DOMINIO = 'escala.hml.invalid'
PREFIXO = 'Escala '
CODIGO = 'ESC'
LOTE = 500
CENTAVOS = Decimal('0.01')

# (status, forma, status_pagamento) com pesos aproximados de uma operação real.
CENARIOS_PEDIDO = [
    ((Pedido.Status.RETIRADO, Pedido.FormaPagamento.DINHEIRO, Pedido.StatusPagamento.APROVADO), 30),
    ((Pedido.Status.RETIRADO, Pedido.FormaPagamento.PIX, Pedido.StatusPagamento.APROVADO), 15),
    ((Pedido.Status.RETIRADO, Pedido.FormaPagamento.CARTAO, Pedido.StatusPagamento.APROVADO), 10),
    ((Pedido.Status.CANCELADO, Pedido.FormaPagamento.PIX, Pedido.StatusPagamento.CANCELADO), 8),
    ((Pedido.Status.CANCELADO, Pedido.FormaPagamento.DINHEIRO, Pedido.StatusPagamento.CANCELADO), 7),
    ((Pedido.Status.PRONTO, Pedido.FormaPagamento.DINHEIRO, Pedido.StatusPagamento.PENDENTE), 8),
    ((Pedido.Status.CONFIRMADO, Pedido.FormaPagamento.PIX, Pedido.StatusPagamento.APROVADO), 8),
    ((Pedido.Status.CONFIRMADO, Pedido.FormaPagamento.DINHEIRO, Pedido.StatusPagamento.PENDENTE), 7),
    ((Pedido.Status.PENDENTE, Pedido.FormaPagamento.DINHEIRO, Pedido.StatusPagamento.PENDENTE), 7),
]


def ambiente_hml():
    """True somente no app HML com banco Neon (mesma regra dos demais comandos HML)."""
    hosts = [host.lower() for host in settings.ALLOWED_HOSTS]
    db_host = str(settings.DATABASES['default'].get('HOST') or '').lower()
    return HOST_HML in hosts and db_host.endswith('.neon.tech')


class Command(BaseCommand):
    help = 'Gera ou remove dados sintéticos de escala somente na HML Neon.'

    def add_arguments(self, parser):
        parser.add_argument('--confirmar-hml', action='store_true', help='Confirma a execução na HML.')
        parser.add_argument('--remover', action='store_true', help='Remove somente os dados sintéticos.')
        parser.add_argument('--categorias', type=int, default=120)
        parser.add_argument('--produtos', type=int, default=3100)
        parser.add_argument('--promocoes', type=int, default=300)
        parser.add_argument('--usuarios', type=int, default=3100)
        parser.add_argument('--pedidos', type=int, default=3200)
        parser.add_argument('--semente', type=int, default=2026)

    def handle(self, *args, **options):
        # Falhar fechado: nunca rodar fora da HML Neon.
        if not ambiente_hml():
            raise CommandError('Ambiente não é a HML Neon esperada. Nenhum dado foi alterado.')
        if not options['confirmar_hml']:
            raise CommandError('Use --confirmar-hml para executar. Nenhum dado foi alterado.')

        if options['remover']:
            totais = remover_dados_escala()
            self.stdout.write(self.style.SUCCESS(f'Dados de escala removidos: {totais}'))
            return

        if Produto.objects.filter(codigo__startswith=CODIGO).exists():
            raise CommandError('Já existem dados de escala. Rode --remover antes de gerar de novo.')
        if options['produtos'] > 0 and options['categorias'] < 1:
            raise CommandError('Produtos exigem pelo menos uma categoria.')

        totais = gerar_dados_escala(random.Random(options['semente']), options)
        self.stdout.write(self.style.SUCCESS(f'Dados de escala gerados: {totais}'))


@transaction.atomic
def gerar_dados_escala(rng, opcoes):
    agora = timezone.now()
    hoje = timezone.localdate()

    categorias = Categoria.objects.bulk_create([
        Categoria(
            nome=f'{PREFIXO}Categoria {i:04d}',
            slug=f'escala-categoria-{i:04d}',
            descricao='Categoria sintética para teste de escala.',
            ordem=1000 + i,
            ativa=i % 10 != 0,
        )
        for i in range(1, opcoes['categorias'] + 1)
    ], batch_size=LOTE)

    produtos = []
    for i in range(1, opcoes['produtos'] + 1):
        preco = (Decimal(rng.randint(150, 4500)) / 100).quantize(CENTAVOS)
        produtos.append(Produto(
            codigo=f'{CODIGO}{i:05d}',
            nome=f'{PREFIXO}Produto {i:05d}',
            slug=f'escala-produto-{i:05d}',
            descricao='Produto sintético para teste de escala.',
            categoria=categorias[(i - 1) % len(categorias)],
            preco=preco,
            preco_custo=(preco * Decimal('0.45')).quantize(CENTAVOS),
            estoque=0 if i % 15 == 0 else rng.randint(1, 200),
            estoque_minimo=5,
            ativo=i % 12 != 0,
        ))
    produtos = Produto.objects.bulk_create(produtos, batch_size=LOTE)

    promocoes = []
    for indice, produto in enumerate(produtos[:opcoes['promocoes']]):
        inicio = hoje + timedelta(days=(-60, -5, 10)[indice % 3])
        promocoes.append(Promocao(
            produto=produto,
            preco_promocional=(produto.preco * Decimal('0.8')).quantize(CENTAVOS),
            data_inicio=inicio,
            data_fim=inicio + timedelta(days=20),
        ))
    Promocao.objects.bulk_create(promocoes, batch_size=LOTE)

    senha_inutilizavel = make_password(None)
    usuarios = get_user_model().objects.bulk_create([
        get_user_model()(
            email=f'cliente{i:05d}@{DOMINIO}',
            name=f'Cliente Escala {i:05d}',
            password=senha_inutilizavel,
            is_active=i % 20 != 0,
            email_verified=True,
        )
        for i in range(1, opcoes['usuarios'] + 1)
    ], batch_size=LOTE)

    total_itens = 0
    pedidos_criados = 0
    vendaveis = [produto for produto in produtos if produto.ativo]
    if usuarios and vendaveis and opcoes['pedidos'] > 0:
        cenarios, pesos = zip(*CENARIOS_PEDIDO)
        pedidos = []
        for _ in range(opcoes['pedidos']):
            status, forma, status_pagamento = rng.choices(cenarios, weights=pesos)[0]
            pedidos.append(Pedido(
                usuario=rng.choice(usuarios),
                status=status,
                forma_pagamento=forma,
                status_pagamento=status_pagamento,
                estoque_devolvido=status == Pedido.Status.CANCELADO,
            ))
        pedidos = Pedido.objects.bulk_create(pedidos, batch_size=LOTE)

        itens = []
        for pedido in pedidos:
            for produto in rng.sample(vendaveis, k=min(len(vendaveis), rng.randint(1, 3))):
                itens.append(ItemPedido(
                    pedido=pedido, produto=produto, quantidade=rng.randint(1, 3), preco_unitario=produto.preco,
                ))
            # auto_now_add ignora o valor no insert: espalha as datas depois.
            momento = agora - timedelta(days=rng.randint(0, 120), minutes=rng.randint(0, 600))
            pedido.data = momento
            pedido.status_atualizado_em = momento + timedelta(minutes=rng.randint(5, 90))
        ItemPedido.objects.bulk_create(itens, batch_size=LOTE)
        Pedido.objects.bulk_update(pedidos, ['data', 'status_atualizado_em'], batch_size=LOTE)
        total_itens = len(itens)
        pedidos_criados = len(pedidos)

    return {
        'categorias': len(categorias),
        'produtos': len(produtos),
        'promocoes': len(promocoes),
        'usuarios': len(usuarios),
        'pedidos': pedidos_criados,
        'itens': total_itens,
    }


@transaction.atomic
def remover_dados_escala():
    pedidos, _ = Pedido.objects.filter(usuario__email__endswith=f'@{DOMINIO}').delete()
    promocoes, _ = Promocao.objects.filter(produto__codigo__startswith=CODIGO).delete()
    produtos, _ = Produto.objects.filter(codigo__startswith=CODIGO).delete()
    categorias, _ = Categoria.objects.filter(nome__startswith=PREFIXO, produtos__isnull=True).delete()
    usuarios, _ = get_user_model().objects.filter(email__endswith=f'@{DOMINIO}').delete()
    return {
        'pedidos_e_itens': pedidos,
        'promocoes': promocoes,
        'produtos': produtos,
        'categorias': categorias,
        'usuarios': usuarios,
    }
