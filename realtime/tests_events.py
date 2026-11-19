"""PR6A.2: sinais pós-commit com isolamento e fallback, sem Redis real."""
import asyncio
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase, override_settings

from chat.models import Conversa, Mensagem
from chat.services.chat import marcar_lidas
from core.models import User
from notificacoes.models import Notificacao
from pedidos.models import Pedido
from realtime.events import ADMIN_GROUP, _enviar_com_limite, publicar_evento


class PublicacaoReativaTestCase(TestCase):
    def setUp(self):
        # Não gerar sinais na preparação dos dados, mesmo com env de staging.
        with override_settings(REALTIME_ENABLED=False):
            self.cliente = User.objects.create_user(
                email='eventos-cliente@example.com', password='Senha!123',
                is_active=True, email_verified=True,
            )
            self.outro_cliente = User.objects.create_user(
                email='eventos-outro@example.com', password='Senha!123',
                is_active=True, email_verified=True,
            )
            self.admin = User.objects.create_user(
                email='eventos-admin@example.com', password='Senha!123',
                is_active=True, is_staff=True, email_verified=True,
            )
            self.pedido = Pedido.objects.create(usuario=self.cliente)

    @override_settings(REALTIME_ENABLED=False)
    @patch('realtime.events._entregar')
    def test_desativado_nao_agenda_eventos(self, entregar):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            Pedido.objects.create(usuario=self.cliente)
            self.pedido.status = Pedido.Status.CONFIRMADO
            self.pedido.save(update_fields=['status'])
        self.assertEqual(callbacks, [])
        entregar.assert_not_called()

    @override_settings(REALTIME_ENABLED=True)
    @patch('realtime.events._entregar')
    def test_novo_pedido_emite_somente_para_admin_e_dono_apos_commit(self, entregar):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            novo = Pedido.objects.create(usuario=self.cliente)
            entregar.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        entregar.assert_called_once()
        grupos, payload = entregar.call_args.args
        self.assertEqual(set(grupos), {ADMIN_GROUP, f'pires-usuario-{self.cliente.pk}'})
        self.assertNotIn(f'pires-usuario-{self.outro_cliente.pk}', grupos)
        self.assertEqual(payload['tipo'], 'pedido.criado')
        self.assertEqual(payload['pedido_id'], novo.pk)
        self.assertEqual(payload['v'], 1)
        self.assertEqual(set(payload), {'v', 'tipo', 'pedido_id', 'event_id', 'emitido_em'})
        self.assertNotIn('Senha', str(payload))
        self.assertTrue(payload['event_id'])

    @override_settings(REALTIME_ENABLED=True)
    @patch('realtime.events._entregar')
    def test_status_e_pagamento_invalida_resumo_sem_enviar_credenciais(self, entregar):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.pedido.status = Pedido.Status.CONFIRMADO
            self.pedido.save(update_fields=['status'])
            self.pedido.status_pagamento = Pedido.StatusPagamento.APROVADO
            self.pedido.save(update_fields=['status_pagamento'])
            self.pedido.estoque_devolvido = True
            self.pedido.save(update_fields=['estoque_devolvido'])
            entregar.assert_not_called()
        self.assertEqual(len(callbacks), 2)
        self.assertEqual(entregar.call_count, 2)
        self.assertTrue(all(chamada.args[1]['tipo'] == 'pedido.atualizado'
                            for chamada in entregar.call_args_list))
        self.assertNotEqual(
            entregar.call_args_list[0].args[1]['event_id'],
            entregar.call_args_list[1].args[1]['event_id'],
        )

    @override_settings(REALTIME_ENABLED=True)
    @patch('realtime.events._entregar')
    def test_rollback_reverte_publicacao(self, entregar):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            try:
                with transaction.atomic():
                    self.pedido.status = Pedido.Status.PRONTO
                    self.pedido.save(update_fields=['status'])
                    raise ValueError('rollback de teste')
            except ValueError:
                pass
        self.assertEqual(callbacks, [])
        entregar.assert_not_called()

    @override_settings(REALTIME_ENABLED=True)
    @patch('realtime.events._entregar')
    def test_chat_e_notificacao_separam_grupos_sem_expor_texto(self, entregar):
        with override_settings(REALTIME_ENABLED=False):
            conversa = Conversa.objects.create(pedido=self.pedido)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            Mensagem.objects.create(
                conversa=conversa, autor=self.cliente,
                enviada_pela_padaria=False,
                texto='Não publique endereço nem texto desta mensagem',
            )
            Notificacao.objects.create(
                usuario=self.cliente, pedido=self.pedido,
                mensagem='Informação particular somente para meu usuário',
            )
            entregar.assert_not_called()
        self.assertEqual(len(callbacks), 2)
        (chat_groups, chat_payload), (notif_groups, notif_payload) = [
            chamada.args for chamada in entregar.call_args_list
        ]
        self.assertEqual(chat_payload['tipo'], 'chat.mensagem_nova')
        self.assertEqual(set(chat_groups), {ADMIN_GROUP, f'pires-usuario-{self.cliente.pk}'})
        self.assertEqual(notif_payload['tipo'], 'notificacao.alterada')
        self.assertEqual(set(notif_groups), {f'pires-usuario-{self.cliente.pk}'})
        self.assertNotIn('Informação particular', str(notif_payload))
        self.assertNotIn('endereço', str(chat_payload))

    @override_settings(REALTIME_ENABLED=True)
    @patch('realtime.events._entregar')
    def test_marcacao_em_lote_de_chat_atualiza_chat_e_notificacao(self, entregar):
        with override_settings(REALTIME_ENABLED=False):
            conversa = Conversa.objects.create(pedido=self.pedido)
            Mensagem.objects.create(
                conversa=conversa, autor=self.admin,
                enviada_pela_padaria=True, texto='Bom dia!',
            )
            Notificacao.objects.create(
                usuario=self.cliente, pedido=self.pedido,
                mensagem=f'Nova mensagem da padaria sobre o pedido #{self.pedido.pk}.',
            )
        with self.captureOnCommitCallbacks(execute=True):
            resultado = marcar_lidas(self.pedido, self.cliente)
        self.assertEqual(resultado, 1)
        tipos = [chamada.args[1]['tipo'] for chamada in entregar.call_args_list]
        self.assertIn('chat.leitura_atualizada', tipos)
        self.assertIn('notificacao.alterada', tipos)
        self.assertNotIn('chat.mensagem_nova', tipos)

    @override_settings(REALTIME_ENABLED=True)
    @patch('realtime.events._entregar')
    def test_marcacao_em_lote_de_notificacoes_e_idempotente(self, entregar):
        from rest_framework.test import APIClient

        with override_settings(REALTIME_ENABLED=False):
            Notificacao.objects.create(
                usuario=self.cliente, pedido=self.pedido, mensagem='Aviso',
            )
        client = APIClient()
        client.force_authenticate(user=self.cliente)
        with self.captureOnCommitCallbacks(execute=True):
            resposta = client.post('/api/notificacoes/marcar_todas_lidas/')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(entregar.call_count, 1)
        self.assertEqual(entregar.call_args.args[1]['tipo'], 'notificacao.alterada')
        entregar.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            resposta = client.post('/api/notificacoes/marcar_todas_lidas/')
        self.assertEqual(resposta.status_code, 200)
        entregar.assert_not_called()

    @override_settings(REALTIME_ENABLED=True)
    @patch('realtime.events._entregar')
    def test_evento_invalido_e_sem_destinatario_nao_e_emitido(self, entregar):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            publicar_evento('evento.desconhecido', usuario_id=self.cliente.pk)
            publicar_evento('pedido.atualizado')
        self.assertEqual(callbacks, [])
        entregar.assert_not_called()

    def test_envio_limitado_transporta_so_sinalizacao(self):
        class CamadaFalsa:
            def __init__(self):
                self.enviados = []

            async def group_send(self, grupo, mensagem):
                self.enviados.append((grupo, mensagem))

        camada = CamadaFalsa()
        payload = {'v': 1, 'tipo': 'pedido.atualizado', 'pedido_id': 1, 'event_id': 'a'}
        grupos = (ADMIN_GROUP, f'pires-usuario-{self.cliente.pk}')
        asyncio.run(_enviar_com_limite(camada, grupos, payload))
        self.assertEqual({grupo for grupo, _ in camada.enviados}, set(grupos))
        self.assertTrue(all(msg == {'type': 'realtime.event', 'payload': payload}
                            for _, msg in camada.enviados))

    @override_settings(REALTIME_ENABLED=True)
    def test_falha_de_redis_nao_reverte_operacao(self):
        from realtime.events import _entregar

        with patch('realtime.events.get_channel_layer', side_effect=OSError('redis indisponível')):
            # Best effort: a API HTTP deve continuar mesmo sem transporte WS.
            _entregar((ADMIN_GROUP,), {'tipo': 'pedido.atualizado'})
