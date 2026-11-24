"""Filtros e paginação administrativos para a futura fila Kanban."""

from rest_framework import status
from rest_framework.test import APITestCase

from pedidos.models import ItemPedido, Pedido
from .base import CriaUsuariosEProdutosMixin


class ListagemPedidosAdministrativosTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    url = '/api/pedidos/'

    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()

    def test_paginacao_servidor_preserva_contagem_e_acesso_a_ultima_pagina(self):
        Pedido.objects.bulk_create(
            [Pedido(usuario=self.aluno, status=Pedido.Status.PENDENTE) for _ in range(205)]
        )
        self.client.force_authenticate(user=self.admin)

        primeira = self.client.get(self.url, {'page_size': 100, 'page': 1, 'status': 'pendente'})
        ultima = self.client.get(self.url, {'page_size': 100, 'page': 3, 'status': 'pendente'})

        self.assertEqual(primeira.status_code, status.HTTP_200_OK)
        self.assertEqual(primeira.data['count'], 205)
        self.assertEqual(len(primeira.data['results']), 100)
        self.assertIsNotNone(primeira.data['next'])
        self.assertEqual(ultima.status_code, status.HTTP_200_OK)
        self.assertEqual(ultima.data['count'], 205)
        self.assertEqual(len(ultima.data['results']), 5)
        self.assertIsNone(ultima.data['next'])

        primeira_ids = {p['id'] for p in primeira.data['results']}
        ultima_ids = {p['id'] for p in ultima.data['results']}
        self.assertTrue(primeira_ids.isdisjoint(ultima_ids))

    def test_busca_por_cliente_produto_e_id_sem_repetir_pedido(self):
        self.aluno.name = 'Jaque Oliveira'
        self.aluno.save(update_fields=['name'])
        pedido = Pedido.objects.create(usuario=self.aluno)
        ItemPedido.objects.create(pedido=pedido, produto=self.coxinha, quantidade=1, preco_unitario=8)
        ItemPedido.objects.create(pedido=pedido, produto=self.coxinha, quantidade=1, preco_unitario=8)
        Pedido.objects.create(usuario=self.outro_aluno)

        self.client.force_authenticate(user=self.admin)
        for termo in ['Jaque', 'coxinha', str(pedido.id)]:
            with self.subTest(termo=termo):
                resposta = self.client.get(self.url, {'busca': termo})
                self.assertEqual(resposta.status_code, status.HTTP_200_OK)
                self.assertEqual(resposta.data['count'], 1)
                self.assertEqual([item['id'] for item in resposta.data['results']], [pedido.id])

    def test_pagamento_e_status_combinam_sem_considerar_outros_status(self):
        esperado = Pedido.objects.create(
            usuario=self.aluno,
            status=Pedido.Status.PENDENTE,
            status_pagamento=Pedido.StatusPagamento.PROCESSANDO,
        )
        Pedido.objects.create(
            usuario=self.aluno,
            status=Pedido.Status.CONFIRMADO,
            status_pagamento=Pedido.StatusPagamento.PROCESSANDO,
        )
        Pedido.objects.create(
            usuario=self.aluno,
            status=Pedido.Status.PENDENTE,
            status_pagamento=Pedido.StatusPagamento.APROVADO,
        )

        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(self.url, {'status': 'pendente', 'pagamento': 'processando'})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['count'], 1)
        self.assertEqual(resposta.data['results'][0]['id'], esperado.id)

    def test_busca_nunca_permite_aluno_acessar_pedidos_de_outra_conta(self):
        pedido_alheio = Pedido.objects.create(usuario=self.outro_aluno)
        Pedido.objects.create(usuario=self.aluno)
        self.client.force_authenticate(user=self.aluno)

        resposta = self.client.get(self.url, {'busca': str(pedido_alheio.id)})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            pedido_alheio.id,
            [p['id'] for p in resposta.data['results']],
        )
        detalhe = self.client.get(f'/api/pedidos/{pedido_alheio.id}/')
        self.assertEqual(detalhe.status_code, status.HTTP_404_NOT_FOUND)

    def test_filtros_de_listagem_nao_restringem_detalhes(self):
        pedido = Pedido.objects.create(usuario=self.aluno)
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(
            f'/api/pedidos/{pedido.id}/',
            {'busca': 'nao-existe', 'pagamento': 'processando'},
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['id'], pedido.id)

    def test_busca_excessiva_e_pagamento_invalido_sao_rejeitados(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(self.url, {'busca': '9' * 120})
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('busca', resposta.data)

        resposta = self.client.get(self.url, {'pagamento': 'desconhecido'})
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pagamento', resposta.data)
