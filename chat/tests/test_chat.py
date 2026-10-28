"""Testes do chat por pedido (cliente dono do pedido ↔ administração)."""

from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from chat.models import Conversa, Mensagem
from notificacoes.models import Notificacao
from pedidos.models import Pedido
from pedidos.tests.base import CriaUsuariosEProdutosMixin


class ChatBaseTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    def setUp(self):
        cache.clear()
        self.criar_usuarios()
        self.pedido = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.CONFIRMADO)
        self.pedido_do_outro = Pedido.objects.create(usuario=self.outro_aluno, status=Pedido.Status.CONFIRMADO)

    def url_chat(self, pedido):
        return f'/api/chat/{pedido.id}/'

    def url_mensagens(self, pedido):
        return f'/api/chat/{pedido.id}/mensagens/'

    def url_marcar_lidas(self, pedido):
        return f'/api/chat/{pedido.id}/marcar_lidas/'

    def enviar(self, usuario, pedido, texto='Olá'):
        self.client.force_authenticate(user=usuario)
        return self.client.post(self.url_mensagens(pedido), {'texto': texto}, format='json')


class PermissoesChatTestCase(ChatBaseTestCase):
    def test_anonimo_nao_acessa(self):
        resposta = self.client.get(self.url_chat(self.pedido))
        assert resposta.status_code == status.HTTP_401_UNAUTHORIZED

    def test_dono_ve_chat_vazio(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get(self.url_chat(self.pedido))

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data['pedido'] == self.pedido.id
        assert resposta.data['mensagens'] == []
        assert resposta.data['somente_leitura'] is False

    def test_outro_cliente_nao_le_chat(self):
        self.enviar(self.aluno, self.pedido, 'segredo do aluno')
        self.client.force_authenticate(user=self.outro_aluno)
        resposta = self.client.get(self.url_chat(self.pedido))

        assert resposta.status_code == status.HTTP_404_NOT_FOUND

    def test_outro_cliente_nao_envia_no_pedido_alheio(self):
        resposta = self.enviar(self.outro_aluno, self.pedido, 'intruso')

        assert resposta.status_code == status.HTTP_404_NOT_FOUND
        assert not Mensagem.objects.exists()

    def test_outro_cliente_nao_marca_lidas_no_pedido_alheio(self):
        self.client.force_authenticate(user=self.outro_aluno)
        resposta = self.client.post(self.url_marcar_lidas(self.pedido))

        assert resposta.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_le_chat_de_qualquer_pedido(self):
        self.enviar(self.aluno, self.pedido, 'Tem coxinha?')
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(self.url_chat(self.pedido))

        assert resposta.status_code == status.HTTP_200_OK
        assert [m['texto'] for m in resposta.data['mensagens']] == ['Tem coxinha?']

    def test_nao_lidas_do_cliente_ignora_pedido_alheio(self):
        self.enviar(self.admin, self.pedido_do_outro, 'mensagem para o outro')
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get('/api/chat/nao_lidas/')

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data == {'total': 0, 'por_pedido': []}


class EnvioMensagemTestCase(ChatBaseTestCase):
    def test_cliente_envia_mensagem(self):
        resposta = self.enviar(self.aluno, self.pedido, '  Posso retirar às 10h?  ')

        assert resposta.status_code == status.HTTP_201_CREATED
        assert resposta.data['texto'] == 'Posso retirar às 10h?'
        assert resposta.data['minha'] is True
        assert resposta.data['enviada_pela_padaria'] is False
        assert Conversa.objects.filter(pedido=self.pedido).count() == 1

    def test_mensagem_do_admin_marcada_como_da_padaria(self):
        resposta = self.enviar(self.admin, self.pedido, 'Seu pedido sai em 5 minutos.')

        assert resposta.status_code == status.HTTP_201_CREATED
        assert resposta.data['enviada_pela_padaria'] is True

        self.client.force_authenticate(user=self.aluno)
        mensagem = self.client.get(self.url_chat(self.pedido)).data['mensagens'][0]
        assert mensagem['minha'] is False
        assert mensagem['enviada_pela_padaria'] is True

    def test_resposta_nao_expoe_email_do_autor(self):
        self.enviar(self.admin, self.pedido, 'Oi')
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get(self.url_chat(self.pedido))

        assert 'admin@teste.com' not in str(resposta.data)

    def test_texto_vazio_e_recusado(self):
        resposta = self.enviar(self.aluno, self.pedido, '   ')
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST
        assert 'texto' in resposta.data

    @override_settings(CHAT_MENSAGEM_TAMANHO_MAXIMO=10)
    def test_texto_acima_do_limite_e_recusado(self):
        resposta = self.enviar(self.aluno, self.pedido, 'x' * 11)
        assert resposta.status_code == status.HTTP_400_BAD_REQUEST
        assert 'texto' in resposta.data

    def test_html_e_guardado_como_texto_puro(self):
        resposta = self.enviar(self.aluno, self.pedido, '<b>oi</b>')

        assert resposta.status_code == status.HTTP_201_CREATED
        assert resposta.data['texto'] == '<b>oi</b>'

    def test_caracteres_de_controle_sao_removidos(self):
        resposta = self.enviar(self.aluno, self.pedido, 'linha 1\r\nlinha\x1b2\x07')

        assert resposta.status_code == status.HTTP_201_CREATED
        assert resposta.data['texto'] == 'linha 1\nlinha2'

    def test_cliente_nao_forja_autor_padaria(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.post(
            self.url_mensagens(self.pedido),
            {'texto': 'oi', 'enviada_pela_padaria': True, 'autor': self.admin.id},
            format='json',
        )

        assert resposta.status_code == status.HTTP_201_CREATED
        mensagem = Mensagem.objects.get()
        assert mensagem.autor == self.aluno
        assert mensagem.enviada_pela_padaria is False

    def test_throttle_de_envio(self):
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'chat_mensagem': '2/min'}):
            assert self.enviar(self.aluno, self.pedido, '1').status_code == status.HTTP_201_CREATED
            assert self.enviar(self.aluno, self.pedido, '2').status_code == status.HTTP_201_CREATED
            assert self.enviar(self.aluno, self.pedido, '3').status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_mensagens_em_ordem_cronologica(self):
        self.enviar(self.aluno, self.pedido, 'primeira')
        self.enviar(self.admin, self.pedido, 'segunda')
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get(self.url_chat(self.pedido))

        assert [m['texto'] for m in resposta.data['mensagens']] == ['primeira', 'segunda']


class NaoLidasTestCase(ChatBaseTestCase):
    def test_mensagem_do_admin_conta_como_nao_lida_para_o_cliente(self):
        self.enviar(self.admin, self.pedido, 'a')
        self.enviar(self.admin, self.pedido, 'b')
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get('/api/chat/nao_lidas/')

        assert resposta.data == {'total': 2, 'por_pedido': [{'pedido': self.pedido.id, 'nao_lidas': 2}]}

    def test_mensagem_propria_nao_conta_como_nao_lida(self):
        self.enviar(self.aluno, self.pedido, 'a')
        self.client.force_authenticate(user=self.aluno)

        assert self.client.get('/api/chat/nao_lidas/').data['total'] == 0

    def test_admin_ve_nao_lidas_de_todos_os_clientes(self):
        self.enviar(self.aluno, self.pedido, 'a')
        self.enviar(self.outro_aluno, self.pedido_do_outro, 'b')
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get('/api/chat/nao_lidas/')

        esperado = sorted([self.pedido.id, self.pedido_do_outro.id])
        assert resposta.data == {
            'total': len(esperado),
            'por_pedido': [{'pedido': pedido_id, 'nao_lidas': 1} for pedido_id in esperado],
        }

    def test_chat_informa_nao_lidas_do_leitor(self):
        self.enviar(self.admin, self.pedido, 'a')
        self.client.force_authenticate(user=self.aluno)

        assert self.client.get(self.url_chat(self.pedido)).data['nao_lidas'] == 1

    def test_marcar_lidas_zera_contador_do_cliente(self):
        self.enviar(self.admin, self.pedido, 'a')
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.post(self.url_marcar_lidas(self.pedido))

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data == {'marcadas': 1}
        assert self.client.get('/api/chat/nao_lidas/').data['total'] == 0
        assert Mensagem.objects.get().lida_em is not None

    def test_cliente_marcar_lidas_nao_marca_as_proprias(self):
        self.enviar(self.aluno, self.pedido, 'minha')
        self.client.force_authenticate(user=self.aluno)
        self.client.post(self.url_marcar_lidas(self.pedido))

        self.client.force_authenticate(user=self.admin)
        assert self.client.get('/api/chat/nao_lidas/').data['total'] == 1

    def test_admin_marcar_lidas_zera_contador_do_admin(self):
        self.enviar(self.aluno, self.pedido, 'a')
        self.client.force_authenticate(user=self.admin)
        self.client.post(self.url_marcar_lidas(self.pedido))

        assert self.client.get('/api/chat/nao_lidas/').data['total'] == 0

    def test_marcar_lidas_sem_conversa_responde_zero(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.post(self.url_marcar_lidas(self.pedido))

        assert resposta.status_code == status.HTTP_200_OK
        assert resposta.data == {'marcadas': 0}


class NotificacaoChatTestCase(ChatBaseTestCase):
    def test_mensagem_do_admin_notifica_o_cliente(self):
        self.enviar(self.admin, self.pedido, 'Pode retirar.')

        notificacao = Notificacao.objects.get(usuario=self.aluno)
        assert notificacao.pedido == self.pedido
        assert f'#{self.pedido.id}' in notificacao.mensagem

    def test_varias_mensagens_nao_duplicam_notificacao_nao_lida(self):
        self.enviar(self.admin, self.pedido, 'a')
        self.enviar(self.admin, self.pedido, 'b')

        assert Notificacao.objects.filter(usuario=self.aluno).count() == 1

    def test_nova_notificacao_depois_de_lida_a_anterior(self):
        self.enviar(self.admin, self.pedido, 'a')
        Notificacao.objects.update(lida=True)
        self.enviar(self.admin, self.pedido, 'b')

        assert Notificacao.objects.filter(usuario=self.aluno, lida=False).count() == 1

    def test_mensagem_do_cliente_nao_gera_notificacao(self):
        self.enviar(self.aluno, self.pedido, 'oi')

        assert not Notificacao.objects.exists()

    def test_ler_o_chat_marca_notificacao_do_chat_como_lida(self):
        self.enviar(self.admin, self.pedido, 'a')
        self.client.force_authenticate(user=self.aluno)
        self.client.post(self.url_marcar_lidas(self.pedido))

        assert not Notificacao.objects.filter(usuario=self.aluno, lida=False).exists()


@override_settings(CHAT_PRAZO_APOS_ENCERRAMENTO_HORAS=24)
class SomenteLeituraTestCase(ChatBaseTestCase):
    def encerrar(self, status_pedido, horas_atras):
        self.pedido.status = status_pedido
        self.pedido.status_atualizado_em = timezone.now() - timedelta(hours=horas_atras)
        self.pedido.save()

    def test_retirado_dentro_do_prazo_aceita_mensagem(self):
        self.encerrar(Pedido.Status.RETIRADO, horas_atras=2)

        assert self.enviar(self.aluno, self.pedido).status_code == status.HTTP_201_CREATED

    def test_retirado_apos_prazo_fica_somente_leitura(self):
        self.encerrar(Pedido.Status.RETIRADO, horas_atras=25)
        resposta = self.enviar(self.aluno, self.pedido)

        assert resposta.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in resposta.data
        assert not Mensagem.objects.exists()

    def test_cancelado_apos_prazo_bloqueia_admin_tambem(self):
        self.encerrar(Pedido.Status.CANCELADO, horas_atras=30)

        assert self.enviar(self.admin, self.pedido).status_code == status.HTTP_400_BAD_REQUEST

    def test_chat_informa_somente_leitura_e_prazo(self):
        self.encerrar(Pedido.Status.RETIRADO, horas_atras=25)
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get(self.url_chat(self.pedido))

        assert resposta.data['somente_leitura'] is True
        assert resposta.data['encerra_em'] is not None

    def test_pedido_ativo_nao_tem_prazo(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get(self.url_chat(self.pedido))

        assert resposta.data['encerra_em'] is None

    def test_mensagens_antigas_continuam_legiveis(self):
        self.enviar(self.aluno, self.pedido, 'histórico')
        self.encerrar(Pedido.Status.RETIRADO, horas_atras=48)
        self.client.force_authenticate(user=self.aluno)

        assert [m['texto'] for m in self.client.get(self.url_chat(self.pedido)).data['mensagens']] == ['histórico']
