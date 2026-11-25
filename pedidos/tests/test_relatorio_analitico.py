"""Relatório analítico: agregação SQL, precisão histórica, segurança e datas locais."""

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from pedidos.models import ItemPedido, Pedido

from .base import CriaUsuariosEProdutosMixin


SAO_PAULO = ZoneInfo('America/Sao_Paulo')


class RelatorioAnaliticoAdminTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    url = '/api/pedidos/relatorio_analitico_admin/'

    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()

    def consultar(self, inicio='2026-11-18', fim='2026-11-19'):
        return self.client.get(self.url, {'data_inicio': inicio, 'data_fim': fim})

    def pedido(self, *, momento, forma=Pedido.FormaPagamento.DINHEIRO,
               status_pedido=Pedido.Status.RETIRADO, itens=None):
        pedido = Pedido.objects.create(
            usuario=self.aluno,
            status=status_pedido,
            forma_pagamento=forma,
        )
        Pedido.objects.filter(pk=pedido.pk).update(status_atualizado_em=momento)
        for produto, quantidade, preco in (itens or []):
            ItemPedido.objects.create(
                pedido=pedido, produto=produto, quantidade=quantidade,
                preco_unitario=Decimal(preco),
            )
        return pedido

    def instante(self, dia, hora=12, minuto=0):
        return datetime.fromisoformat(dia).replace(hour=hora, minute=minuto, tzinfo=SAO_PAULO)

    def test_permissao_somente_admin_sem_expor_dados_pessoais(self):
        anonima = self.consultar()
        self.assertIn(anonima.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.client.force_authenticate(user=self.aluno)
        self.assertEqual(self.consultar().status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.admin)
        resposta = self.consultar()
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['resumo']['total_pedidos'], 0)
        self.assertNotIn('usuario', str(resposta.data))
        self.assertNotIn('email', str(resposta.data))

    def test_periodos_invalidos_limite_e_parametros(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_400_BAD_REQUEST)
        for inicio, fim in [
            ('2026-11-20', '2026-11-19'),
            ('19-11-2026', '2026-11-19'),
            ('20261118', '2026-11-19'),
            ('2026-02-30', '2026-03-01'),
            ('2025-01-01', '2026-01-02'),
            ('0001-01-01', '0001-01-01'),
            ('9999-12-31', '9999-12-31'),
        ]:
            with self.subTest(inicio=inicio, fim=fim):
                self.assertEqual(self.consultar(inicio, fim).status_code, status.HTTP_400_BAD_REQUEST)
        valido = self.consultar('2025-01-01', '2026-01-01')
        self.assertEqual(valido.status_code, status.HTTP_200_OK)
        self.assertEqual(len(valido.data['serie_diaria']), 366)

    def test_periodo_vazio_gera_zeros_em_todos_os_dias_sem_variacao_artificial(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.consultar('2026-11-18', '2026-11-20')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['resumo'], {
            'total_vendido': '0.00', 'total_pedidos': 0, 'itens_vendidos': 0,
            'ticket_medio': '0.00',
        })
        self.assertEqual([x['data'] for x in resposta.data['serie_diaria']], [
            '2026-11-18', '2026-11-19', '2026-11-20',
        ])
        self.assertTrue(all(x['total_vendido'] == '0.00' for x in resposta.data['serie_diaria']))
        self.assertTrue(all(v is None for v in resposta.data['comparacao']['variacao_percentual'].values()))
        self.assertEqual(len(resposta.data['formas_pagamento']), 3)

    def test_precos_historicos_contagem_por_pedido_e_comparacao(self):
        self.pedido(
            momento=self.instante('2026-11-19'), forma=Pedido.FormaPagamento.PIX,
            itens=[(self.coxinha, 3, '3.33'), (self.suco, 2, '2.50')],
        )
        self.pedido(
            momento=self.instante('2026-11-18'), forma=Pedido.FormaPagamento.DINHEIRO,
            itens=[(self.coxinha, 1, '5.00')],
        )
        self.pedido(
            momento=self.instante('2026-11-17'), forma=Pedido.FormaPagamento.CARTAO,
            itens=[(self.suco, 1, '10.00')],
        )
        self.coxinha.preco = Decimal('49.99')
        self.coxinha.save()
        self.pedido(
            momento=self.instante('2026-11-19'), status_pedido=Pedido.Status.CANCELADO,
            itens=[(self.suco, 1, '999.00')],
        )
        self.pedido(
            momento=self.instante('2026-11-19'), status_pedido=Pedido.Status.PENDENTE,
            itens=[(self.suco, 10, '999.00')],
        )

        self.client.force_authenticate(user=self.admin)
        resposta = self.consultar()
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.assertEqual(resposta.data['resumo'], {
            'total_vendido': '19.99', 'total_pedidos': 2,
            'itens_vendidos': 6, 'ticket_medio': '10.00',
        })
        self.assertEqual(resposta.data['comparacao']['periodo_anterior'], {
            'data_inicio': '2026-11-16', 'data_fim': '2026-11-17',
        })
        self.assertEqual(resposta.data['comparacao']['anterior'], {
            'total_vendido': '10.00', 'total_pedidos': 1,
            'itens_vendidos': 1, 'ticket_medio': '10.00',
        })
        self.assertEqual(resposta.data['comparacao']['variacao_percentual'], {
            'total_vendido': '99.9', 'total_pedidos': '100.0',
            'itens_vendidos': '500.0', 'ticket_medio': '0.0',
        })
        self.assertEqual([p['total_vendido'] for p in resposta.data['serie_diaria']], [
            '5.00', '14.99',
        ])
        pagamentos = {p['forma_pagamento']: p for p in resposta.data['formas_pagamento']}
        self.assertEqual(pagamentos['pix']['total_vendido'], '14.99')
        self.assertEqual(pagamentos['pix']['total_pedidos'], 1)
        self.assertEqual(pagamentos['pix']['percentual_pedidos'], '50.0')
        self.assertEqual(pagamentos['dinheiro']['total_vendido'], '5.00')
        self.assertEqual(pagamentos['cartao']['total_pedidos'], 0)
        self.assertEqual(sum(p['total_pedidos'] for p in pagamentos.values()), 2)

    def test_virada_da_meia_noite_de_sao_paulo_e_periodo_inclusivo(self):
        self.pedido(
            momento=datetime(2026, 11, 19, 1, 30, tzinfo=ZoneInfo('UTC')),
            itens=[(self.coxinha, 1, '7.00')],
        )
        self.pedido(
            momento=datetime(2026, 11, 19, 3, 15, tzinfo=ZoneInfo('UTC')),
            itens=[(self.suco, 1, '6.00')],
        )
        self.client.force_authenticate(user=self.admin)
        dia_18 = self.consultar('2026-11-18', '2026-11-18')
        dia_19 = self.consultar('2026-11-19', '2026-11-19')
        self.assertEqual(dia_18.data['resumo']['total_vendido'], '7.00')
        self.assertEqual(dia_19.data['resumo']['total_vendido'], '6.00')
        self.assertEqual(dia_19.data['comparacao']['anterior']['total_vendido'], '7.00')
        self.assertEqual(dia_19.data['comparacao']['variacao_percentual']['total_vendido'], '-14.3')

    def test_pedido_retirado_sem_itens_ainda_conta_com_faturamento_zero(self):
        self.pedido(momento=self.instante('2026-11-19'))
        self.client.force_authenticate(user=self.admin)
        resposta = self.consultar('2026-11-19', '2026-11-19')
        self.assertEqual(resposta.data['resumo']['total_pedidos'], 1)
        self.assertEqual(resposta.data['resumo']['total_vendido'], '0.00')
        self.assertEqual(resposta.data['resumo']['ticket_medio'], '0.00')

    def test_mais_de_3000_pedidos_sem_consultar_cada_pedido(self):
        instante = self.instante('2026-11-19')
        pedidos = Pedido.objects.bulk_create([
            Pedido(
                usuario=self.aluno, status=Pedido.Status.RETIRADO,
                forma_pagamento=Pedido.FormaPagamento.DINHEIRO,
            )
            for _ in range(3001)
        ], batch_size=250)
        Pedido.objects.filter(pk__in=[p.pk for p in pedidos]).update(status_atualizado_em=instante)
        ItemPedido.objects.bulk_create([
            ItemPedido(pedido=pedido, produto=self.coxinha, quantidade=1, preco_unitario=Decimal('2.00'))
            for pedido in pedidos
        ], batch_size=250)

        self.client.force_authenticate(user=self.admin)
        with CaptureQueriesContext(connection) as queries:
            resposta = self.consultar('2026-11-19', '2026-11-19')
        self.assertEqual(resposta.status_code, status.HTTP_200_OK, resposta.data)
        self.assertEqual(resposta.data['resumo']['total_pedidos'], 3001)
        self.assertEqual(resposta.data['resumo']['total_vendido'], '6002.00')
        self.assertEqual(resposta.data['resumo']['itens_vendidos'], 3001)
        self.assertLessEqual(len(queries), 6, 'O relatório não pode consultar pedidos individualmente')
