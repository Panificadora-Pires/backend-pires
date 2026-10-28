"""
Provedor de respostas por regras + FAQ.

O texto do cliente é normalizado (minúsculas, sem acentos) e comparado com palavras-chave. Ganha a
intenção com mais palavras encontradas; em empate, vale a FAQ. Intenções que dependem de dados
(pedidos do usuário e disponibilidade de produtos) são respondidas aqui, sempre restritas ao usuário logado.
"""

import re
import unicodedata

from django.conf import settings

from catalogo.models import Produto
from chat.services.chat import chat_somente_leitura
from chatbot.models import PerguntaFrequente
from pedidos.models import Pedido

from .provedores import ProvedorResposta, Resposta

STATUS_ATIVOS = (Pedido.Status.PENDENTE, Pedido.Status.CONFIRMADO, Pedido.Status.PRONTO)
MAXIMO_PEDIDOS = 5
MAXIMO_PRODUTOS = 5
MAXIMO_SUGESTOES_APOS_RESPOSTA = 3
# Uma pergunta curta só com o nome do produto ("coxinha?") também conta como disponibilidade.
MAXIMO_PALAVRAS_PERGUNTA_CURTA = 3
PESO_PRODUTO_ENCONTRADO = 2
# Palavras menores que isso no nome do produto ("de", "e") não identificam o produto.
TAMANHO_MINIMO_PALAVRA_PRODUTO = 4

PALAVRAS_MEUS_PEDIDOS = [
    'meu pedido',
    'meus pedidos',
    'status',
    'cade',
    'acompanhar',
    'andamento',
    'ficou pronto',
    'esta pronto',
]
PALAVRAS_FALAR_COM_PADARIA = [
    'falar com',
    'conversar',
    'atendente',
    'atendimento',
    'humano',
    'vendedor',
    'chat',
    'reclam*',
]
PALAVRAS_DISPONIBILIDADE = ['tem', 'ainda tem', 'estoque', 'disponivel', 'disponiveis', 'acabou', 'esgot*']
# Palavras do nome do produto que não identificam o produto sozinhas.
PALAVRAS_IGNORADAS_NO_PRODUTO = {'com', 'sem', 'para', 'tipo'}

TEXTO_STATUS = {
    Pedido.Status.PENDENTE: 'recebido, aguardando confirmação da padaria',
    Pedido.Status.CONFIRMADO: 'confirmado e em preparo',
    Pedido.Status.PRONTO: 'pronto para retirada! Mostre o QR Code no balcão',
    Pedido.Status.RETIRADO: 'retirado',
    Pedido.Status.CANCELADO: 'cancelado',
}


def normalizar(texto):
    sem_acentos = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode('ascii')
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', sem_acentos.lower()).split())


def _padrao(palavra_chave):
    prefixo = palavra_chave.endswith('*')
    termo = normalizar(palavra_chave.rstrip('*'))
    if not termo:
        return None
    return re.compile(r'\b' + re.escape(termo) + ('' if prefixo else r'\b'))


def pontuar(palavras_chave, texto_normalizado):
    """Soma o número de palavras de cada palavra-chave encontrada (expressões valem mais)."""

    pontos = 0
    for palavra_chave in palavras_chave:
        padrao = _padrao(palavra_chave)
        if padrao and padrao.search(texto_normalizado):
            pontos += len(normalizar(palavra_chave.rstrip('*')).split())
    return pontos


class _Valores(dict):
    def __missing__(self, chave):
        return '{' + chave + '}'


def renderizar_resposta(texto):
    """Troca {minutos_retirada} e {minutos_pagamento}; texto com chaves inválidas volta como está."""

    valores = _Valores(
        minutos_retirada=settings.PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS,
        minutos_pagamento=settings.PAGAMENTO_TEMPO_LIMITE_MINUTOS,
    )
    try:
        return texto.format_map(valores)
    except (ValueError, IndexError):
        return texto


def acao_intencao(rotulo, valor):
    return {'tipo': 'intencao', 'rotulo': rotulo, 'valor': valor}


def acao_chat(pedido):
    return {'tipo': 'chat', 'rotulo': f'Conversar sobre o pedido #{pedido.id}', 'pedido': pedido.id}


def acao_rota(rotulo, rota):
    return {'tipo': 'rota', 'rotulo': rotulo, 'rota': rota}


ACAO_MEUS_PEDIDOS = acao_intencao('Status do meu pedido', 'meus_pedidos')
ACAO_FALAR_COM_PADARIA = acao_intencao('Falar com a padaria', 'falar_com_padaria')


def resumo_pedido(pedido):
    return {
        'id': pedido.id,
        'status': pedido.status,
        'status_display': pedido.get_status_display(),
        'total': str(pedido.total),
        'data': pedido.data.isoformat(),
    }


def resumo_produto(produto):
    return {
        'id': produto.id,
        'nome': produto.nome,
        'preco': str(produto.preco),
        'disponivel': produto.estoque > 0,
    }


class ProvedorRegras(ProvedorResposta):
    def responder(self, *, usuario, texto=None, intencao=None):
        if intencao:
            return self._responder_intencao(usuario, intencao)
        return self._responder_texto(usuario, texto or '')

    # ---- Escolha da intenção -------------------------------------------------

    def _responder_intencao(self, usuario, intencao):
        dinamicas = {
            'inicio': self._inicio,
            'meus_pedidos': self._meus_pedidos,
            'falar_com_padaria': self._falar_com_padaria,
        }
        if intencao in dinamicas:
            return dinamicas[intencao](usuario)

        faq = PerguntaFrequente.objects.filter(chave=intencao, ativa=True).first()
        if faq:
            return self._responder_faq(faq)
        return self._fallback()

    def _responder_texto(self, usuario, texto):
        texto_normalizado = normalizar(texto)
        melhor_faq, melhor_pontos = None, 0

        for faq in PerguntaFrequente.objects.filter(ativa=True):
            pontos = pontuar(faq.lista_palavras_chave(), texto_normalizado)
            if pontos > melhor_pontos:
                melhor_faq, melhor_pontos = faq, pontos

        produtos = self._produtos_citados(texto_normalizado)
        pontos_disponibilidade = pontuar(PALAVRAS_DISPONIBILIDADE, texto_normalizado)
        pergunta_curta = len(texto_normalizado.split()) <= MAXIMO_PALAVRAS_PERGUNTA_CURTA
        if produtos and (pontos_disponibilidade or pergunta_curta):
            pontos_disponibilidade += PESO_PRODUTO_ENCONTRADO

        dinamicas = [
            (pontuar(PALAVRAS_MEUS_PEDIDOS, texto_normalizado), lambda: self._meus_pedidos(usuario)),
            (pontuar(PALAVRAS_FALAR_COM_PADARIA, texto_normalizado), lambda: self._falar_com_padaria(usuario)),
            (pontos_disponibilidade, lambda: self._disponibilidade(produtos)),
        ]
        melhor_dinamica = None
        for pontos, responder in dinamicas:
            # Empate com a FAQ: vale a FAQ (pontuação estritamente maior para a intenção dinâmica).
            if pontos > melhor_pontos:
                melhor_dinamica, melhor_pontos = responder, pontos

        if melhor_dinamica:
            return melhor_dinamica()
        if melhor_faq:
            return self._responder_faq(melhor_faq)
        return self._fallback()

    # ---- Respostas -------------------------------------------------------------

    def _sugestoes_faq(self, excluir=None, limite=None):
        sugeridas = PerguntaFrequente.objects.filter(ativa=True, sugerida=True)
        if excluir:
            sugeridas = sugeridas.exclude(chave=excluir)
        if limite:
            sugeridas = sugeridas[:limite]
        return [acao_intencao(faq.pergunta, faq.chave) for faq in sugeridas]

    def _inicio(self, usuario):
        primeiro_nome = (usuario.name or '').split(' ')[0]
        saudacao = f'Oi, {primeiro_nome}!' if primeiro_nome else 'Oi!'
        return Resposta(
            intencao='inicio',
            texto=f'{saudacao} Sou o assistente da Pires. Escolha um assunto ou escreva sua dúvida.',
            acoes=[*self._sugestoes_faq(), ACAO_MEUS_PEDIDOS, ACAO_FALAR_COM_PADARIA],
        )

    def _responder_faq(self, faq):
        return Resposta(
            intencao=faq.chave,
            texto=renderizar_resposta(faq.resposta),
            acoes=[
                *self._sugestoes_faq(excluir=faq.chave, limite=MAXIMO_SUGESTOES_APOS_RESPOSTA),
                ACAO_FALAR_COM_PADARIA,
            ],
        )

    def _fallback(self):
        return Resposta(
            intencao='fallback',
            texto=(
                'Não entendi sua pergunta. Escolha um dos assuntos abaixo ou, se precisar de alguém da equipe, '
                'fale com a padaria pelo chat do seu pedido.'
            ),
            acoes=[*self._sugestoes_faq(), ACAO_MEUS_PEDIDOS, ACAO_FALAR_COM_PADARIA],
        )

    def _meus_pedidos(self, usuario):
        pedidos = Pedido.objects.filter(usuario=usuario).prefetch_related('itens').order_by('-data')
        ativos = list(pedidos.filter(status__in=STATUS_ATIVOS)[:MAXIMO_PEDIDOS])

        if ativos:
            linhas = [f'Pedido #{pedido.id}: {TEXTO_STATUS[pedido.status]}.' for pedido in ativos]
            return Resposta(
                intencao='meus_pedidos',
                texto='\n'.join(linhas),
                pedidos=[resumo_pedido(pedido) for pedido in ativos],
                acoes=[
                    *[acao_chat(pedido) for pedido in ativos],
                    acao_rota('Abrir Meus pedidos', 'pedidos'),
                ],
            )

        ultimo = pedidos.first()
        if ultimo:
            return Resposta(
                intencao='meus_pedidos',
                texto=(
                    f'Você não tem pedidos em andamento. O último foi o #{ultimo.id}, '
                    f'{TEXTO_STATUS[ultimo.status]}.'
                ),
                pedidos=[resumo_pedido(ultimo)],
                acoes=[acao_rota('Abrir Meus pedidos', 'pedidos'), ACAO_FALAR_COM_PADARIA],
            )

        return Resposta(
            intencao='meus_pedidos',
            texto='Você ainda não fez nenhum pedido. Escolha seus produtos no cardápio.',
            acoes=[acao_rota('Ver cardápio', 'cardapio')],
        )

    def _falar_com_padaria(self, usuario):
        recentes = Pedido.objects.filter(usuario=usuario).order_by('-data')[:MAXIMO_PEDIDOS]
        com_chat_aberto = [pedido for pedido in recentes if not chat_somente_leitura(pedido)]

        if com_chat_aberto:
            return Resposta(
                intencao='falar_com_padaria',
                texto='A conversa com a padaria fica dentro de cada pedido. Escolha o pedido:',
                acoes=[acao_chat(pedido) for pedido in com_chat_aberto],
            )

        return Resposta(
            intencao='falar_com_padaria',
            texto=(
                'A conversa com a padaria fica dentro de cada pedido, e você não tem um pedido com chat aberto. '
                'Depois de fazer um pedido, toque em Mensagens no card dele em Meus pedidos.'
            ),
            acoes=[acao_rota('Ver cardápio', 'cardapio')],
        )

    def _produtos_citados(self, texto_normalizado):
        palavras_do_texto = set(texto_normalizado.split())
        encontrados = []

        for produto in Produto.objects.filter(ativo=True).order_by('nome'):
            palavras_do_nome = [
                palavra
                for palavra in normalizar(produto.nome).split()
                if len(palavra) >= TAMANHO_MINIMO_PALAVRA_PRODUTO and palavra not in PALAVRAS_IGNORADAS_NO_PRODUTO
            ]
            # Aceita o plural simples ("coxinhas" acha "Coxinha").
            coincidencias = sum(
                1 for palavra in palavras_do_nome if palavra in palavras_do_texto or f'{palavra}s' in palavras_do_texto
            )
            if coincidencias:
                encontrados.append((coincidencias, produto))

        encontrados.sort(key=lambda par: -par[0])
        return [produto for _, produto in encontrados[:MAXIMO_PRODUTOS]]

    def _disponibilidade(self, produtos):
        if not produtos:
            return Resposta(
                intencao='disponibilidade',
                texto='Não encontrei esse produto no cardápio de hoje. Confira tudo o que está disponível no cardápio.',
                acoes=[acao_rota('Ver cardápio', 'cardapio'), ACAO_FALAR_COM_PADARIA],
            )

        linhas = [
            f'{produto.nome}: {"disponível" if produto.estoque > 0 else "esgotado no momento"}.' for produto in produtos
        ]
        return Resposta(
            intencao='disponibilidade',
            texto='\n'.join(linhas),
            produtos=[resumo_produto(produto) for produto in produtos],
            acoes=[acao_rota('Ver cardápio', 'cardapio'), ACAO_FALAR_COM_PADARIA],
        )
