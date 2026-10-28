"""Testes do chatbot de ajuda (regras + FAQ editável)."""

from unittest import mock

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from chatbot.models import PerguntaFrequente
from chatbot.services.provedores import ProvedorResposta, Resposta
from pedidos.models import ItemPedido, Pedido
from pedidos.tests.base import CriaUsuariosEProdutosMixin

URL_INICIO = '/api/chatbot/inicio/'
URL_MENSAGEM = '/api/chatbot/mensagem/'


class ProvedorDeTeste(ProvedorResposta):
    """Simula um provedor futuro (ex.: IA) plugado por configuração."""

    def responder(self, *, usuario, texto=None, intencao=None):
        return Resposta(intencao='teste', texto=f'eco: {texto}')


class ChatbotBaseTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        cache.clear()
        self.criar_usuarios()
        self.criar_produtos()
        self.client.force_authenticate(user=self.aluno)

    def perguntar(self, texto=None, intencao=None):
        corpo = {}
        if texto is not None:
            corpo['texto'] = texto
        if intencao is not None:
            corpo['intencao'] = intencao
        return self.client.post(URL_MENSAGEM, corpo, format='json')

    def acoes_do_tipo(self, resposta, tipo):
        return [acao for acao in resposta.data['acoes'] if acao['tipo'] == tipo]

    def criar_pedido(self, usuario, status_pedido, produto=None):
        pedido = Pedido.objects.create(usuario=usuario, status=status_pedido)
        ItemPedido.objects.create(pedido=pedido, produto=produto or self.coxinha, quantidade=1, preco_unitario=8)
        return pedido


class AcessoChatbotTestCase(ChatbotBaseTestCase):
    def test_inicio_exige_login(self):
        self.client.force_authenticate(user=None)
        assert self.client.get(URL_INICIO).status_code == status.HTTP_401_UNAUTHORIZED

    def test_mensagem_exige_login(self):
        self.client.force_authenticate(user=None)
        assert self.perguntar('oi').status_code == status.HTTP_401_UNAUTHORIZED

    def test_sem_texto_e_sem_intencao_e_recusado(self):
        assert self.perguntar().status_code == status.HTTP_400_BAD_REQUEST

    def test_texto_so_com_espacos_e_recusado(self):
        assert self.perguntar('   ').status_code == status.HTTP_400_BAD_REQUEST

    def test_texto_longo_demais_e_recusado(self):
        assert self.perguntar('a' * 301).status_code == status.HTTP_400_BAD_REQUEST

    def test_throttle_de_mensagens(self):
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'chatbot': '2/min'}):
            assert self.perguntar('oi').status_code == status.HTTP_200_OK
            assert self.perguntar('oi').status_code == status.HTTP_200_OK
            assert self.perguntar('oi').status_code == status.HTTP_429_TOO_MANY_REQUESTS


class InicioTestCase(ChatbotBaseTestCase):
    def test_inicio_sugere_perguntas_da_faq(self):
        resposta = self.client.get(URL_INICIO)

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data['intencao'] == 'inicio'
        valores = {acao['valor'] for acao in self.acoes_do_tipo(resposta, 'intencao')}
        assert {'retirada', 'pagamento', 'meus_pedidos', 'falar_com_padaria'} <= valores

    def test_faq_nao_sugerida_fica_fora_do_inicio(self):
        PerguntaFrequente.objects.filter(chave='pagamento').update(sugerida=False)
        resposta = self.client.get(URL_INICIO)

        assert 'pagamento' not in {acao['valor'] for acao in self.acoes_do_tipo(resposta, 'intencao')}


class FaqTestCase(ChatbotBaseTestCase):
    def test_faq_inicial_vem_da_migration(self):
        chaves = set(PerguntaFrequente.objects.values_list('chave', flat=True))
        assert {'retirada', 'pagamento', 'prazo_retirada', 'cancelamento', 'horario'} <= chaves

    def test_pergunta_livre_encontra_a_faq(self):
        resposta = self.perguntar('Como funciona a retirada do lanche?')

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data['intencao'] == 'retirada'
        assert 'QR Code' in resposta.data['texto']

    def test_botao_envia_a_intencao_direto(self):
        resposta = self.perguntar(intencao='pagamento')

        assert resposta.data['intencao'] == 'pagamento'
        assert 'Pix' in resposta.data['texto']

    def test_ignora_acentos_e_maiusculas(self):
        assert self.perguntar('CANCELAMENTO').data['intencao'] == 'cancelamento'
        assert self.perguntar('dá pra pagar no cartão?').data['intencao'] == 'pagamento'

    @override_settings(PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS=20, PAGAMENTO_TEMPO_LIMITE_MINUTOS=30)
    def test_resposta_usa_os_prazos_configurados(self):
        texto = self.perguntar(intencao='prazo_retirada').data['texto']

        assert '20 minutos' in texto
        assert '30 minutos' in texto

    def test_faq_cadastrada_no_admin_passa_a_responder(self):
        PerguntaFrequente.objects.create(
            chave='wifi', pergunta='Tem wi-fi?', palavras_chave='wifi, wi-fi, internet', resposta='Não temos wi-fi.'
        )

        resposta = self.perguntar('vocês têm internet?')
        assert resposta.data['intencao'] == 'wifi'
        assert resposta.data['texto'] == 'Não temos wi-fi.'

    def test_palavra_com_asterisco_aceita_variacoes(self):
        PerguntaFrequente.objects.create(
            chave='encomenda', pergunta='Encomendas', palavras_chave='encomend*', resposta='Ainda não aceitamos.'
        )

        assert self.perguntar('fazem encomendas?').data['intencao'] == 'encomenda'

    def test_faq_inativa_nao_responde(self):
        PerguntaFrequente.objects.filter(chave='retirada').update(ativa=False)

        assert self.perguntar('como funciona a retirada?').data['intencao'] != 'retirada'
        assert self.perguntar(intencao='retirada').data['intencao'] == 'fallback'

    def test_chaves_seguras_na_resposta_com_chaves_quebradas(self):
        PerguntaFrequente.objects.create(
            chave='quebrada',
            pergunta='Quebrada',
            palavras_chave='quebrada',
            resposta='Texto com {chave_inexistente} e {',
        )

        resposta = self.perguntar(intencao='quebrada')
        assert resposta.status_code == status.HTTP_200_OK
        assert 'Texto com' in resposta.data['texto']

    def test_toda_resposta_oferece_falar_com_a_padaria(self):
        for resposta in (self.perguntar(intencao='retirada'), self.perguntar('asdfgh qwerty')):
            valores = {acao['valor'] for acao in self.acoes_do_tipo(resposta, 'intencao')}
            assert 'falar_com_padaria' in valores

    def test_chave_reservada_nao_pode_virar_faq(self):
        pergunta = PerguntaFrequente(chave='meus_pedidos', pergunta='x', palavras_chave='x', resposta='x')

        campos_com_erro = {}
        try:
            pergunta.full_clean()
        except ValidationError as erro:
            campos_com_erro = erro.message_dict

        assert 'chave' in campos_com_erro


class FallbackTestCase(ChatbotBaseTestCase):
    def test_texto_sem_sentido_cai_no_fallback(self):
        resposta = self.perguntar('asdfgh qwerty')

        assert resposta.data['intencao'] == 'fallback'
        assert 'Não entendi' in resposta.data['texto']
        assert self.acoes_do_tipo(resposta, 'intencao')

    def test_intencao_desconhecida_cai_no_fallback(self):
        assert self.perguntar(intencao='nao_existe').data['intencao'] == 'fallback'


class MeusPedidosTestCase(ChatbotBaseTestCase):
    def test_mostra_so_os_pedidos_do_usuario(self):
        meu = self.criar_pedido(self.aluno, Pedido.Status.CONFIRMADO)
        self.criar_pedido(self.outro_aluno, Pedido.Status.PRONTO)

        resposta = self.perguntar('cadê meu pedido?')

        assert resposta.data['intencao'] == 'meus_pedidos'
        assert [pedido['id'] for pedido in resposta.data['pedidos']] == [meu.id]
        assert resposta.data['pedidos'][0]['status'] == 'confirmado'

    def test_pedido_ativo_oferece_chat_do_pedido(self):
        meu = self.criar_pedido(self.aluno, Pedido.Status.PRONTO)

        resposta = self.perguntar(intencao='meus_pedidos')

        assert [acao['pedido'] for acao in self.acoes_do_tipo(resposta, 'chat')] == [meu.id]
        assert 'pronto' in resposta.data['texto'].lower()

    def test_sem_pedidos_ativos_mostra_o_ultimo_finalizado(self):
        antigo = self.criar_pedido(self.aluno, Pedido.Status.RETIRADO)

        resposta = self.perguntar(intencao='meus_pedidos')

        assert [pedido['id'] for pedido in resposta.data['pedidos']] == [antigo.id]

    def test_sem_nenhum_pedido_indica_o_cardapio(self):
        resposta = self.perguntar(intencao='meus_pedidos')

        assert resposta.data['pedidos'] == []
        assert [acao['rota'] for acao in self.acoes_do_tipo(resposta, 'rota')] == ['cardapio']


class FalarComPadariaTestCase(ChatbotBaseTestCase):
    def test_lista_chat_dos_pedidos_ativos_do_usuario(self):
        meu = self.criar_pedido(self.aluno, Pedido.Status.PENDENTE)
        self.criar_pedido(self.outro_aluno, Pedido.Status.PENDENTE)

        resposta = self.perguntar('quero falar com um atendente')

        assert resposta.data['intencao'] == 'falar_com_padaria'
        assert [acao['pedido'] for acao in self.acoes_do_tipo(resposta, 'chat')] == [meu.id]

    def test_sem_pedido_explica_que_o_chat_fica_no_pedido(self):
        resposta = self.perguntar(intencao='falar_com_padaria')

        assert self.acoes_do_tipo(resposta, 'chat') == []
        assert 'pedido' in resposta.data['texto']


class DisponibilidadeTestCase(ChatbotBaseTestCase):
    def test_produto_com_estoque_aparece_disponivel(self):
        resposta = self.perguntar('tem coxinha?')

        assert resposta.data['intencao'] == 'disponibilidade'
        assert resposta.data['produtos'] == [
            {'id': self.coxinha.id, 'nome': 'Coxinha de frango', 'preco': '8.00', 'disponivel': True}
        ]

    def test_produto_sem_estoque_aparece_esgotado(self):
        self.suco.estoque = 0
        self.suco.save()

        produto = self.perguntar('ainda tem suco de laranja?').data['produtos'][0]
        assert produto['nome'] == 'Suco de laranja'
        assert produto['disponivel'] is False

    def test_produto_inativo_nao_aparece(self):
        self.coxinha.ativo = False
        self.coxinha.save()

        assert self.perguntar('tem coxinha?').data['produtos'] == []

    def test_resposta_nao_revela_quantidade_em_estoque(self):
        assert 'estoque' not in self.perguntar('tem coxinha?').data['produtos'][0]

    def test_produto_desconhecido_indica_o_cardapio(self):
        resposta = self.perguntar('tem pastel?')

        assert resposta.data['intencao'] == 'disponibilidade'
        assert resposta.data['produtos'] == []
        assert [acao['rota'] for acao in self.acoes_do_tipo(resposta, 'rota')] == ['cardapio']


class ProvedorPlugavelTestCase(ChatbotBaseTestCase):
    @override_settings(CHATBOT_PROVEDOR='chatbot.tests.test_chatbot.ProvedorDeTeste')
    def test_provedor_configurado_responde(self):
        resposta = self.perguntar('oi')

        assert resposta.data['intencao'] == 'teste'
        assert resposta.data['texto'] == 'eco: oi'
        assert resposta.data['pedidos'] == []
