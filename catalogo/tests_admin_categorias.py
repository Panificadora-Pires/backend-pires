"""Paginação administrativa de categorias, independente do cardápio público."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from catalogo.models import Categoria

User = get_user_model()


class AdminCategoriasTestCase(APITestCase):
    lista = '/api/categorias/admin_listagem/'
    resumo = '/api/categorias/resumo_admin/'

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin-categorias@example.com', password='senhaSegura123',
            is_staff=True,
        )
        self.cliente = User.objects.create_user(
            email='cliente-categorias@example.com', password='senhaSegura123',
        )

    def autenticar(self):
        self.client.force_authenticate(user=self.admin)

    def test_acesso_reservado_e_somente_leitura(self):
        for caminho in (self.lista, self.resumo):
            with self.subTest(caminho=caminho):
                self.assertIn(self.client.get(caminho).status_code, (401, 403))
                self.client.force_authenticate(user=self.cliente)
                self.assertEqual(self.client.get(caminho).status_code, 403)
                self.client.force_authenticate(user=None)
        self.autenticar()
        self.assertEqual(self.client.post(self.lista, {}).status_code, 405)

    def test_filtros_ordenacao_e_indicadores_globais(self):
        bebidas = Categoria.objects.create(
            nome='Bebidas', descricao='Sucos e cafés', ordem=3, ativa=True,
        )
        doces = Categoria.objects.create(
            nome='Doces', descricao='Bolos e pães doces', ordem=1, ativa=False,
        )
        salgados = Categoria.objects.create(
            nome='Salgados', descricao='Coxinhas', ordem=1, ativa=True,
        )
        self.autenticar()
        primeira = self.client.get(self.lista, {'page_size': 2})
        segunda = self.client.get(self.lista, {'page_size': 2, 'page': 2})
        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(primeira.data['count'], 3)
        self.assertEqual(primeira.data['total_pages'], 2)
        self.assertEqual([item['id'] for item in primeira.data['results']], [doces.pk, salgados.pk])
        self.assertEqual([item['id'] for item in segunda.data['results']], [bebidas.pk])
        self.assertEqual(self.client.get(self.lista, {'busca': 'CAFE'}).data['results'][0]['id'], bebidas.pk)
        self.assertEqual(self.client.get(self.lista, {'busca': 'PAES'}).data['results'][0]['id'], doces.pk)
        self.assertEqual(self.client.get(self.lista, {'busca': 'salgados'}).data['results'][0]['id'], salgados.pk)
        self.assertEqual(self.client.get(self.lista, {'situacao': 'inativa'}).data['count'], 1)
        self.assertEqual(
            self.client.get(self.lista, {'busca': 'Bebidas', 'situacao': 'inativa'}).data['count'],
            0,
        )
        self.assertEqual(self.client.get(self.resumo).data, {
            'total': 3, 'ativas': 2, 'inativas': 1,
        })
        self.assertEqual(self.client.get('/api/categorias/').status_code, 200)

    def test_parametros_invalidos_nao_produzem_numeros_enganosos(self):
        self.autenticar()
        for filtros in ({'situacao': 'bloqueada'}, {'busca': 'a' * 101}):
            with self.subTest(filtros=filtros):
                self.assertEqual(self.client.get(self.lista, filtros).status_code, 400)

    def test_3001_categorias_sem_carregar_colecao_inteira(self):
        Categoria.objects.bulk_create([
            Categoria(
                nome=f'Categoria {i:04d}', slug=f'categoria-{i:04d}',
                ordem=i, ativa=(i % 2 == 0),
            )
            for i in range(3001)
        ], batch_size=250)
        self.autenticar()
        with CaptureQueriesContext(connection) as queries:
            resposta = self.client.get(self.lista, {'page_size': 18, 'page': 2})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['count'], 3001)
        self.assertEqual(resposta.data['page_size'], 18)
        self.assertEqual(len(resposta.data['results']), 18)
        self.assertLessEqual(len(queries), 6)
        resumo = self.client.get(self.resumo).data
        self.assertEqual(resumo, {'total': 3001, 'ativas': 1501, 'inativas': 1500})
