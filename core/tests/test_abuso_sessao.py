"""PR7A.3 (R-09): abuso de sessão JWT com tokens reais, sem force_authenticate."""
from django.urls import reverse
from rest_framework import status

from core.models import User
from core.tests.base import AuthAPITestCase

SENHA = 'SenhaSessao!2026'


class AbusoSessaoTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email='sessao@example.com',
            password=SENHA,
            email_verified=True,
            is_active=True,
        )

    def login(self):
        resposta = self.client.post(
            reverse('token_obtain_pair'),
            {'email': self.user.email, 'password': SENHA},
            format='json',
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        return resposta.data['access'], resposta.data['refresh']

    def me(self, access):
        return self.client.get('/api/usuarios/me/', HTTP_AUTHORIZATION=f'Bearer {access}')

    def refresh(self, refresh):
        return self.client.post(reverse('token_refresh'), {'refresh': refresh}, format='json')

    def test_conta_desativada_perde_access_antigo(self):
        access, _ = self.login()
        self.assertEqual(self.me(access).status_code, status.HTTP_200_OK)

        self.user.is_active = False
        self.user.save(update_fields=['is_active'])

        self.assertEqual(self.me(access).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_conta_desativada_nao_renova_refresh_antigo(self):
        _, refresh = self.login()

        self.user.is_active = False
        self.user.save(update_fields=['is_active'])

        resposta = self.refresh(refresh)
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('access', resposta.data)

    def test_troca_de_senha_invalida_refresh_antigo(self):
        _, refresh = self.login()

        self.user.set_password('OutraSenha!2026')
        self.user.save()

        resposta = self.refresh(refresh)
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resposta.data['detail'].code, 'password_changed')
        self.assertNotIn('access', resposta.data)

    def test_usuario_apagado_nao_renova_refresh(self):
        _, refresh = self.login()
        self.user.delete()

        resposta = self.refresh(refresh)
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_com_access_no_lugar_do_refresh_e_rejeitado(self):
        access, refresh = self.login()

        resposta = self.client.post(reverse('token_logout'), {'refresh': access}, format='json')
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.refresh(refresh).status_code, status.HTTP_200_OK)

    def test_token_adulterado_e_rejeitado(self):
        access, _ = self.login()
        cabecalho, carga, assinatura = access.split('.')
        adulterado = f'{cabecalho}.{carga}.{assinatura[:-2]}xx'

        self.assertEqual(self.me(adulterado).status_code, status.HTTP_401_UNAUTHORIZED)


class RotasPrivadasSemLoginTests(AuthAPITestCase):
    def test_rotas_privadas_exigem_autenticacao(self):
        rotas = [
            ('get', '/api/usuarios/me/'),
            ('get', '/api/usuarios/'),
            ('get', '/api/pedidos/'),
            ('get', '/api/notificacoes/'),
            ('get', '/api/favoritos/'),
            ('get', '/api/chat/nao_lidas/'),
            ('post', '/api/realtime/ticket/'),
            ('post', '/api/pedidos/checkout_dinheiro/'),
        ]
        for metodo, rota in rotas:
            with self.subTest(rota=rota):
                resposta = getattr(self.client, metodo)(rota, {}, format='json')
                self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
