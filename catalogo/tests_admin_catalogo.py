"""Consulta administrativa paginada do catálogo: permissões, agregados e filtros."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalogo.models import Categoria, Produto, Promocao
from pedidos.models import ItemPedido, Pedido

User = get_user_model()


class CatalogoAdministrativoTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='admin@teste.com', password='senha12345', is_staff=True)
        self.aluno = User.objects.create_user(email='aluno@teste.com', password='senha12345')
        self.categoria = Categoria.objects.create(nome='Salgados', ordem=1)
        self.outra_categoria = Categoria.objects.create(nome='Doces', ordem=2)

    def produto(self, nome, *, estoque=7, estoque_minimo=2, ativo=True, categoria=None):
        return Produto.objects.create(
            nome=nome, categoria=categoria or self.categoria, preco=Decimal('12.00'),
            estoque=estoque, estoque_minimo=estoque_minimo, ativo=ativo,
        )

    def test_ambos_endpoints_exigem_admin(self):
        for rota in ('/api/produtos/admin_catalogo/', '/api/produtos/resumo_admin/'):
            with self.subTest(rota=rota):
                self.assertIn(self.client.get(rota).status_code, (401, 403))
                self.client.force_authenticate(user=self.aluno)
                self.assertEqual(self.client.get(rota).status_code, 403)
                self.client.force_authenticate(user=None)
        # A listagem pública continua disponível ao aluno e não expõe dados internos.
        self.produto('Coxinha')
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get('/api/produtos/')
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('estoque', resposta.data['results'][0])
        self.assertNotIn('estoque_minimo', resposta.data['results'][0])
        self.assertNotIn('preco_custo', resposta.data['results'][0])

    def test_detalhe_interno_so_admin_recebe_custo_e_limite_de_estoque(self):
        item = self.produto('Pão integral', estoque=2, estoque_minimo=8)
        item.preco_custo = Decimal('5.25')
        item.save(update_fields=['preco_custo'])
        caminho = f'/api/produtos/{item.id}/admin_detalhe/'

        self.client.force_authenticate(user=self.aluno)
        self.assertEqual(self.client.get(caminho).status_code, 403)
        publico = self.client.get(f'/api/produtos/{item.id}/')
        self.assertNotIn('preco_custo', publico.data)
        self.assertNotIn('estoque_minimo', publico.data)

        self.client.force_authenticate(user=self.admin)
        interno = self.client.get(caminho)
        self.assertEqual(interno.status_code, 200)
        self.assertEqual(Decimal(interno.data['preco_custo']), Decimal('5.25'))
        self.assertEqual(interno.data['estoque_minimo'], 8)
        self.assertEqual(interno.data['estoque'], 2)

    def test_pagina_traz_dados_completos_e_promocao_vigente(self):
        item = self.produto('Coxinha especial', estoque=1, estoque_minimo=3)
        Promocao.objects.create(
            produto=item, preco_promocional=Decimal('9.50'),
            data_inicio=timezone.localdate() - timedelta(days=1),
            data_fim=timezone.localdate() + timedelta(days=1),
        )
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get('/api/produtos/admin_catalogo/', {'page_size': 12})
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['count'], 1)
        self.assertEqual(resposta.data['page_size'], 12)
        item_api = resposta.data['results'][0]
        self.assertEqual(item_api['codigo'], item.codigo)
        self.assertEqual(item_api['estoque'], 1)
        self.assertEqual(item_api['estoque_minimo'], 3)
        self.assertTrue(item_api['estoque_baixo'])
        self.assertTrue(item_api['ativo'])
        self.assertTrue(item_api['em_promocao'])
        self.assertEqual(Decimal(str(item_api['preco_atual'])), Decimal('9.50'))
        self.assertNotIn('preco_custo', item_api)

    def test_filtros_e_paginacao_preservam_total_global(self):
        for numero in range(104):
            self.produto(f'Produto {numero:03d}', estoque=0 if numero == 0 else 10)
        self.produto('Bolo de chocolate', categoria=self.outra_categoria, ativo=False)
        self.client.force_authenticate(user=self.admin)
        pagina_um = self.client.get('/api/produtos/admin_catalogo/', {'page': 1, 'page_size': 50})
        pagina_tres = self.client.get('/api/produtos/admin_catalogo/', {'page': 3, 'page_size': 50})
        self.assertEqual((pagina_um.data['count'], len(pagina_um.data['results'])), (105, 50))
        self.assertEqual((pagina_tres.data['count'], len(pagina_tres.data['results'])), (105, 5))
        self.assertEqual(
            self.client.get('/api/produtos/admin_catalogo/', {'busca': 'Bolo'}).data['count'], 1,
        )
        self.assertEqual(
            self.client.get('/api/produtos/admin_catalogo/', {'categoria': self.outra_categoria.pk}).data['count'], 1,
        )
        self.assertEqual(
            self.client.get('/api/produtos/admin_catalogo/', {'situacao': 'inativo'}).data['count'], 1,
        )
        self.assertEqual(
            self.client.get('/api/produtos/admin_catalogo/', {'situacao': 'sem-estoque'}).data['count'], 1,
        )

    def test_resumo_usa_contagens_totais_do_banco_e_nao_da_pagina(self):
        p1 = self.produto('Salgado sem estoque', estoque=0)
        self.produto('Doce inativo', estoque=6, ativo=False)
        p3 = self.produto('Pão promocional', estoque=1, estoque_minimo=1)
        Promocao.objects.create(
            produto=p3, preco_promocional=Decimal('10.00'),
            data_inicio=timezone.localdate(), data_fim=timezone.localdate() + timedelta(days=2),
        )
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get('/api/produtos/resumo_admin/')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['total'], 3)
        self.assertEqual(resposta.data['ativos'], 2)
        self.assertEqual(resposta.data['sem_estoque'], 1)
        self.assertEqual(resposta.data['reposicao'], 2)
        self.assertEqual(resposta.data['em_promocao'], 1)

    def test_parametros_invalidos_retornam_400(self):
        self.client.force_authenticate(user=self.admin)
        for parametros in ({'busca': 'a' * 101}, {'categoria': 'nao-numero'},
                            {'situacao': 'indefinido'}):
            with self.subTest(parametros=parametros):
                resposta = self.client.get('/api/produtos/admin_catalogo/', parametros)
                self.assertEqual(resposta.status_code, 400)

    def test_resumo_promocoes_e_restrito_a_admin(self):
        rota = '/api/promocoes/resumo_admin/'
        self.assertIn(self.client.get(rota).status_code, (401, 403))
        self.client.force_authenticate(user=self.aluno)
        self.assertEqual(self.client.get(rota).status_code, 403)
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(rota)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data, {'total': 0, 'ativas': 0})

    def test_resumo_promocoes_considera_datas_e_nao_depende_de_paginacao(self):
        hoje = timezone.localdate()
        ativos = self.produto('Promoção de hoje')
        futuros = self.produto('Promoção futura')
        passados = self.produto('Promoção encerrada')
        for produto, inicio, fim in (
            (ativos, hoje - timedelta(days=1), hoje + timedelta(days=1)),
            (futuros, hoje + timedelta(days=1), hoje + timedelta(days=3)),
            (passados, hoje - timedelta(days=3), hoje - timedelta(days=1)),
        ):
            Promocao.objects.create(
                produto=produto, preco_promocional=Decimal('9.00'),
                data_inicio=inicio, data_fim=fim,
            )
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get('/api/promocoes/resumo_admin/')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data, {'total': 3, 'ativas': 1})

    def test_ranking_devolve_imagem_sem_precisar_do_catalogo_completo(self):
        produto = self.produto('Brioche de chocolate')
        produto.imagem = 'produtos/ranking.png'
        produto.save(update_fields=['imagem'])
        sem_imagem = self.produto('Suco natural')
        pedido = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.RETIRADO)
        ItemPedido.objects.create(
            pedido=pedido, produto=produto, quantidade=4,
            preco_unitario=Decimal('12.00'),
        )
        ItemPedido.objects.create(
            pedido=pedido, produto=sem_imagem, quantidade=1,
            preco_unitario=Decimal('12.00'),
        )
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get('/api/produtos/mais_vendidos/', {'limite': 3})
        self.assertEqual(resposta.status_code, 200)
        ranking = resposta.data['resultado']
        self.assertEqual(ranking[0]['produto_id'], produto.id)
        self.assertEqual(ranking[0]['quantidade_vendida'], 4)
        self.assertTrue(ranking[0]['produto_imagem'])
        self.assertIn('ranking.png', ranking[0]['produto_imagem'])
        self.assertIsNone(ranking[1]['produto_imagem'])
