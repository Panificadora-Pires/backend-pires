from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import User

from .models import Notificacao


def extrair_resultados(response):
    """
    Aceita tanto respostas paginadas quanto listas simples.
    """

    data = response.data

    if isinstance(data, list):
        return data

    return data.get('results', [])


class NotificacaoAPITests(APITestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            email='notificacoes@example.com',
            password='SenhaForte!2026',
            name='Aluno',
            phone='+5547999999981',
            email_verified=True,
            is_active=True,
        )
        self.outro_usuario = User.objects.create_user(
            email='notificacoes-outro@example.com',
            password='SenhaForte!2026',
            name='Outro',
            phone='+5547999999982',
            email_verified=True,
            is_active=True,
        )

    def test_lista_apenas_notificacoes_do_usuario_logado(self):
        Notificacao.objects.create(
            usuario=self.usuario,
            mensagem='Minha notificação',
        )
        Notificacao.objects.create(
            usuario=self.outro_usuario,
            mensagem='Notificação de outro usuário',
        )
        self.client.force_authenticate(user=self.usuario)

        response = self.client.get(
            reverse('notificacoes-list'),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        resultados = extrair_resultados(response)

        self.assertEqual(len(resultados), 1)
        self.assertEqual(
            resultados[0]['mensagem'],
            'Minha notificação',
        )

    def test_marca_notificacao_como_lida(self):
        notificacao = Notificacao.objects.create(
            usuario=self.usuario,
            mensagem='Pedido pronto',
        )
        self.client.force_authenticate(user=self.usuario)

        response = self.client.patch(
            reverse(
                'notificacoes-marcar-lida',
                kwargs={'pk': notificacao.pk},
            ),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        notificacao.refresh_from_db()
        self.assertTrue(notificacao.lida)

    def test_marca_todas_como_lidas(self):
        Notificacao.objects.create(
            usuario=self.usuario,
            mensagem='Uma',
        )
        Notificacao.objects.create(
            usuario=self.usuario,
            mensagem='Duas',
        )
        self.client.force_authenticate(user=self.usuario)

        response = self.client.post(
            reverse('notificacoes-marcar-todas-lidas'),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
        self.assertFalse(
            Notificacao.objects.filter(
                usuario=self.usuario,
                lida=False,
            ).exists()
        )
