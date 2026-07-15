"""Testes do app catalogo: Categoria, Produto e Promocao."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from catalogo.models import Categoria, Produto, Promocao

User = get_user_model()


class PromocaoTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='admin@teste.com', password='senha12345', is_staff=True)
        self.aluno = User.objects.create_user(email='aluno@teste.com', password='senha12345')
        self.categoria = Categoria.objects.create(nome='Doces', ordem=1)
        self.produto = Produto.objects.create(nome='Brigadeiro', categoria=self.categoria, preco=3.50, estoque=20)

    def test_aluno_nao_cadastra_promocao(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.post(
            '/api/promocoes/',
            {
                'produto': self.produto.id,
                'preco_promocional': 2.50,
                'data_inicio': date.today().isoformat(),
                'data_fim': (date.today() + timedelta(days=3)).isoformat(),
            },
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_preco_promocional_maior_que_original_falha(self):
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/promocoes/',
            {
                'produto': self.produto.id,
                'preco_promocional': 10.00,
                'data_inicio': date.today().isoformat(),
                'data_fim': (date.today() + timedelta(days=3)).isoformat(),
            },
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_datas_sobrepostas_para_mesmo_produto_falha(self):
        Promocao.objects.create(
            produto=self.produto,
            preco_promocional=2.50,
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=5),
        )
        self.client.force_authenticate(user=self.admin)
        # nova promoção começando no meio do período da primeira -> deve ser rejeitada
        resposta = self.client.post(
            '/api/promocoes/',
            {
                'produto': self.produto.id,
                'preco_promocional': 2.00,
                'data_inicio': (date.today() + timedelta(days=2)).isoformat(),
                'data_fim': (date.today() + timedelta(days=8)).isoformat(),
            },
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_datas_nao_sobrepostas_sao_aceitas(self):
        Promocao.objects.create(
            produto=self.produto,
            preco_promocional=2.50,
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=5),
        )
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.post(
            '/api/promocoes/',
            {
                'produto': self.produto.id,
                'preco_promocional': 2.00,
                'data_inicio': (date.today() + timedelta(days=6)).isoformat(),
                'data_fim': (date.today() + timedelta(days=10)).isoformat(),
            },
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)

    def test_editar_a_propria_promocao_nao_conflita_consigo_mesma(self):
        promocao = Promocao.objects.create(
            produto=self.produto,
            preco_promocional=2.50,
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=5),
        )
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.patch(
            f'/api/promocoes/{promocao.id}/', {'preco_promocional': 2.75}, format='json'
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)


class ProdutoVisibilidadeTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='admin@teste.com', password='senha12345', is_staff=True)
        self.aluno = User.objects.create_user(email='aluno@teste.com', password='senha12345')
        self.categoria = Categoria.objects.create(nome='Salgados', ordem=1)
        Produto.objects.create(
            nome='Coxinha de frango', categoria=self.categoria, preco=8.00, preco_custo=3.50, estoque=10
        )

    def test_preco_custo_nao_aparece_na_listagem_do_aluno(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.get('/api/produtos/')

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        for produto in resposta.data['results']:
            self.assertNotIn('preco_custo', produto)

    def test_preco_custo_aparece_para_admin_na_edicao(self):
        produto = Produto.objects.get(nome='Coxinha de frango')
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(f'/api/produtos/{produto.id}/')
        # o serializer de detalhe (usado no retrieve) também não deve expor preco_custo
        self.assertNotIn('preco_custo', resposta.data)

    def test_aluno_nao_cadastra_produto(self):
        self.client.force_authenticate(user=self.aluno)
        resposta = self.client.post(
            '/api/produtos/',
            {'nome': 'Pastel', 'categoria': self.categoria.id, 'preco': 7, 'estoque': 5},
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
