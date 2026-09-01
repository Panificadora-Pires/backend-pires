from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from catalogo.models import Categoria, Produto
from core.models import User

from .models import Favorito


def extrair_resultados(response):
    """
    Aceita tanto respostas paginadas quanto listas simples.

    O projeto já suporta os dois formatos no frontend, então os testes
    não devem acoplar a regra de negócio ao formato do paginator.
    """

    data = response.data

    if isinstance(data, list):
        return data

    return data.get('results', [])


class FavoritoAPITests(APITestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            email='aluno@example.com',
            password='SenhaForte!2026',
            name='Aluno',
            phone='+5547999999991',
            email_verified=True,
            is_active=True,
        )
        self.outro_usuario = User.objects.create_user(
            email='outro@example.com',
            password='SenhaForte!2026',
            name='Outro',
            phone='+5547999999992',
            email_verified=True,
            is_active=True,
        )
        self.categoria = Categoria.objects.create(
            nome='Salgados',
            ativa=True,
        )
        self.produto = Produto.objects.create(
            nome='Coxinha',
            categoria=self.categoria,
            preco='6.50',
            estoque=10,
            ativo=True,
        )

    def test_usuario_pode_adicionar_listar_e_remover_favorito(self):
        self.client.force_authenticate(user=self.usuario)

        create_response = self.client.post(
            reverse('favoritos-list'),
            {'produto': self.produto.id},
            format='json',
        )

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
        )
        self.assertEqual(
            create_response.data['produto_detalhe']['id'],
            self.produto.id,
        )

        list_response = self.client.get(
            reverse('favoritos-list'),
        )

        self.assertEqual(
            list_response.status_code,
            status.HTTP_200_OK,
        )

        resultados = extrair_resultados(list_response)

        self.assertEqual(len(resultados), 1)
        self.assertEqual(
            resultados[0]['produto_detalhe']['id'],
            self.produto.id,
        )

        delete_response = self.client.delete(
            f'/api/favoritos/{self.produto.id}/'
        )

        self.assertEqual(
            delete_response.status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.assertFalse(
            Favorito.objects.filter(
                usuario=self.usuario,
                produto=self.produto,
            ).exists()
        )

    def test_favoritos_sao_isolados_por_usuario(self):
        Favorito.objects.create(
            usuario=self.outro_usuario,
            produto=self.produto,
        )
        self.client.force_authenticate(user=self.usuario)

        response = self.client.get(
            reverse('favoritos-list'),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            len(extrair_resultados(response)),
            0,
        )

    def test_produto_nao_pode_ser_favoritado_duas_vezes(self):
        Favorito.objects.create(
            usuario=self.usuario,
            produto=self.produto,
        )
        self.client.force_authenticate(user=self.usuario)

        response = self.client.post(
            reverse('favoritos-list'),
            {'produto': self.produto.id},
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
