"""Agregações financeiras do Admin: sem carregar pedidos nem preços atuais do catálogo."""

from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.db.models import Count, DecimalField, ExpressionWrapper, F, IntegerField, Sum, Value
from django.db.models.functions import Coalesce, TruncDate

from pedidos.models import Pedido


FUSO = ZoneInfo('America/Sao_Paulo')
CENTAVO = Decimal('0.01')
PERCENTUAL = Decimal('0.1')
CAMPO_VALOR = DecimalField(max_digits=20, decimal_places=2)
FORMAS_PAGAMENTO = (
    Pedido.FormaPagamento.DINHEIRO,
    Pedido.FormaPagamento.PIX,
    Pedido.FormaPagamento.CARTAO,
)


def _moeda(valor):
    return Decimal(str(valor or 0)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _resumo_vazio():
    return {
        'total_vendido': Decimal('0.00'),
        'total_pedidos': 0,
        'itens_vendidos': 0,
    }


def _somar(resumo, *, pedidos, itens, receita):
    resumo['total_pedidos'] += int(pedidos)
    resumo['itens_vendidos'] += int(itens)
    resumo['total_vendido'] += _moeda(receita)


def _serializar_resumo(resumo):
    pedidos = resumo['total_pedidos']
    total = _moeda(resumo['total_vendido'])
    ticket = _moeda(total / pedidos) if pedidos else Decimal('0.00')
    return {
        'total_vendido': str(total),
        'total_pedidos': pedidos,
        'itens_vendidos': resumo['itens_vendidos'],
        'ticket_medio': str(ticket),
    }


def _variacao(atual, anterior):
    anterior_valor = Decimal(str(anterior))
    if anterior_valor == 0:
        return None
    diferenca = (Decimal(str(atual)) - anterior_valor) * 100 / abs(anterior_valor)
    return str(diferenca.quantize(PERCENTUAL, rounding=ROUND_HALF_UP))


def gerar_relatorio_analitico(data_inicio, data_fim):
    """Consulta agrupada por dia local e pagamento, incluindo comparação com período anterior.

    Datas são inclusivas no fuso America/Sao_Paulo. Os preços vêm de ItemPedido,
    não do catálogo atual. Apenas pedidos retirados entram nos agregados.
    """
    duracao = (data_fim - data_inicio).days + 1
    anterior_inicio = data_inicio - timedelta(days=duracao)
    anterior_fim = data_inicio - timedelta(days=1)

    # Intervalo semiaberto permite usar o índice de status+timestamp sem filtrar
    # por __date, e respeita a data civil local na virada de meia-noite.
    primeiro_instante = datetime.combine(anterior_inicio, time.min, tzinfo=FUSO)
    ultimo_instante = datetime.combine(data_fim + timedelta(days=1), time.min, tzinfo=FUSO)

    preco_historico = ExpressionWrapper(
        F('itens__preco_unitario') * F('itens__quantidade'),
        output_field=CAMPO_VALOR,
    )
    linhas = (
        Pedido.objects.filter(
            status=Pedido.Status.RETIRADO,
            status_atualizado_em__gte=primeiro_instante,
            status_atualizado_em__lt=ultimo_instante,
        )
        .order_by()
        .annotate(dia_local=TruncDate('status_atualizado_em', tzinfo=FUSO))
        .values('dia_local', 'forma_pagamento')
        .annotate(
            pedidos=Count('pk', distinct=True),
            itens=Coalesce(Sum('itens__quantidade'), Value(0), output_field=IntegerField()),
            receita=Coalesce(
                Sum(preco_historico, output_field=CAMPO_VALOR),
                Value(Decimal('0.00'), output_field=CAMPO_VALOR),
                output_field=CAMPO_VALOR,
            ),
        )
        .order_by('dia_local', 'forma_pagamento')
    )

    atual = _resumo_vazio()
    anterior = _resumo_vazio()
    por_dia = {}
    por_pagamento = {forma: _resumo_vazio() for forma in FORMAS_PAGAMENTO}

    for linha in linhas:
        dia = linha['dia_local']
        quantidade = linha['pedidos']
        itens = linha['itens']
        receita = linha['receita']
        if dia < data_inicio:
            _somar(anterior, pedidos=quantidade, itens=itens, receita=receita)
            continue
        _somar(atual, pedidos=quantidade, itens=itens, receita=receita)
        resumo_dia = por_dia.setdefault(dia, _resumo_vazio())
        _somar(resumo_dia, pedidos=quantidade, itens=itens, receita=receita)
        forma = linha['forma_pagamento']
        if forma in por_pagamento:
            _somar(por_pagamento[forma], pedidos=quantidade, itens=itens, receita=receita)

    resumo_atual = _serializar_resumo(atual)
    resumo_anterior = _serializar_resumo(anterior)
    variacao = {
        chave: _variacao(resumo_atual[chave], resumo_anterior[chave])
        for chave in ('total_vendido', 'total_pedidos', 'itens_vendidos', 'ticket_medio')
    }
    serie = []
    for indice in range(duracao):
        dia = data_inicio + timedelta(days=indice)
        serie.append({'data': dia.isoformat(), **_serializar_resumo(por_dia.get(dia, _resumo_vazio()))})

    formas = []
    for forma in FORMAS_PAGAMENTO:
        resumo_forma = _serializar_resumo(por_pagamento[forma])
        percentual = (
            Decimal(resumo_forma['total_pedidos']) * 100 / atual['total_pedidos']
            if atual['total_pedidos']
            else Decimal('0')
        )
        formas.append({
            'forma_pagamento': forma,
            'total_pedidos': resumo_forma['total_pedidos'],
            'total_vendido': resumo_forma['total_vendido'],
            'percentual_pedidos': str(percentual.quantize(PERCENTUAL, rounding=ROUND_HALF_UP)),
        })

    return {
        'criterio': (
            'Considera pedidos retirados, pela data de retirada em America/Sao_Paulo. '
            'Valores usam os preços históricos dos itens; não representam dinheiro conciliado.'
        ),
        'periodo': {
            'data_inicio': data_inicio.isoformat(),
            'data_fim': data_fim.isoformat(),
            'dias': duracao,
            'fuso': 'America/Sao_Paulo',
        },
        'resumo': resumo_atual,
        'comparacao': {
            'periodo_anterior': {
                'data_inicio': anterior_inicio.isoformat(),
                'data_fim': anterior_fim.isoformat(),
            },
            'anterior': resumo_anterior,
            'variacao_percentual': variacao,
        },
        'serie_diaria': serie,
        'formas_pagamento': formas,
    }
