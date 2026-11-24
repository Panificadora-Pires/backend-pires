"""Consultas administrativas escaláveis de usuários, sem operações de escrita."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status

from core.models import User
from core.tests.base import AuthAPITestCase


class AdminUsuariosTestCase(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(
            email='admin@example.com', password=self.strong_password,
            name='Responsável',
        )
        self.cliente = User.objects.create_user(
            email='cliente@example.com', password=self.strong_password,
            name='Cliente Teste', is_active=True, email_verified=True,
        )
        self.inativo = User.objects.create_user(
            email='pendente@example.com', password=self.strong_password,
            name='Sem confirmação', is_active=False, email_verified=False,
        )
        self.lista_url = reverse('usuarios-admin-listagem')
        self.resumo_url = reverse('usuarios-resumo-admin')

    def autenticar_admin(self):
        self.client.force_authenticate(user=self.admin)

    def test_listagem_e_resumo_sao_exclusivos_para_administradores(self):
        for url in (self.lista_url, self.resumo_url):
            with self.subTest(url=url, perfil='anonimo'):
                self.client.force_authenticate(user=None)
                self.assertIn(
                    self.client.get(url).status_code,
                    (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
                )
            with self.subTest(url=url, perfil='cliente'):
                self.client.force_authenticate(user=self.cliente)
                self.assertEqual(
                    self.client.get(url).status_code,
                    status.HTTP_403_FORBIDDEN,
                )
        self.autenticar_admin()
        self.assertEqual(self.client.get(self.lista_url).status_code, 200)
        self.assertEqual(self.client.get(self.resumo_url).status_code, 200)

    def test_contadores_sao_globais_e_nao_seguem_filtros(self):
        self.autenticar_admin()
        self.assertEqual(self.client.get(self.resumo_url).data, {
            'total': 3, 'administradores': 1,
            'clientes': 2, 'ativas': 2, 'emails_verificados': 2,
        })
        filtrada = self.client.get(self.lista_url, {'perfil': 'cliente', 'situacao': 'inativa'})
        self.assertEqual(filtrada.status_code, 200)
        self.assertEqual(filtrada.data['count'], 1)
        self.assertEqual(self.client.get(self.resumo_url).data['total'], 3)

    def test_paginacao_e_dados_minimos_sem_credenciais(self):
        self.autenticar_admin()
        resposta = self.client.get(self.lista_url, {'page_size': 2})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['count'], 3)
        self.assertEqual(resposta.data['total_pages'], 2)
        self.assertEqual(resposta.data['page'], 1)
        self.assertEqual(len(resposta.data['results']), 2)
        self.assertIsNotNone(resposta.data['next'])
        dados = resposta.data['results'][0]
        self.assertEqual(set(dados), {
            'id', 'name', 'email', 'is_staff',
            'is_active', 'email_verified', 'last_login',
        })
        for proibido in (
            'phone', 'avatar', 'google_sub', 'groups',
            'password', 'is_superuser', 'has_usable_password',
        ):
            self.assertNotIn(proibido, dados)
        pagina2 = self.client.get(self.lista_url, {'page': 2, 'page_size': 2})
        self.assertEqual(len(pagina2.data['results']), 1)
        self.assertEqual(
            len({u['id'] for u in resposta.data['results'] + pagina2.data['results']}),
            3,
        )

    def test_filtros_por_nome_email_perfil_situacao_e_verificacao(self):
        self.autenticar_admin()
        casos = [
            ({'busca': 'CLIENTE'}, 1, self.cliente.pk),
            ({'busca': '@example.com', 'perfil': 'admin'}, 1, self.admin.pk),
            ({'perfil': 'cliente', 'situacao': 'inativa'}, 1, self.inativo.pk),
            ({'verificacao': 'pendente'}, 1, self.inativo.pk),
            ({'perfil': 'cliente', 'verificacao': 'verificado'}, 1, self.cliente.pk),
        ]
        for filtros, quantidade, usuario_id in casos:
            with self.subTest(filtros=filtros):
                resposta = self.client.get(self.lista_url, filtros)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.data['count'], quantidade)
                self.assertEqual(resposta.data['results'][0]['id'], usuario_id)

        sem_resultado = self.client.get(self.lista_url, {'busca': 'nao-existe'})
        self.assertEqual(sem_resultado.status_code, 200)
        self.assertEqual(sem_resultado.data['count'], 0)
        self.assertEqual(sem_resultado.data['results'], [])

    def test_parametros_invalidos_nao_geram_respostas_enganosas(self):
        self.autenticar_admin()
        for filtro, valor in [
            ('perfil', 'superuser'), ('situacao', 'bloqueado'),
            ('verificacao', 'todos'), ('busca', 'x' * 101),
        ]:
            with self.subTest(filtro=filtro):
                self.assertEqual(
                    self.client.get(self.lista_url, {filtro: valor}).status_code,
                    status.HTTP_400_BAD_REQUEST,
                )

    def test_consulta_sem_escrita_na_api_administrativa(self):
        self.autenticar_admin()
        self.assertEqual(self.client.post(self.lista_url, {}).status_code, 405)
        self.assertEqual(self.client.patch(
            reverse('usuarios-detail', args=[self.cliente.pk]),
            {'is_staff': True}, format='json',
        ).status_code, 405)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.is_staff)

    def test_listagem_com_centenas_de_contas_nao_consulta_uma_por_vez(self):
        User.objects.bulk_create([
            User(email=f'conta{i:04d}@example.com', name=f'Conta {i:04d}',
                 is_staff=False, is_active=True, email_verified=True)
            for i in range(305)
        ], batch_size=100)
        self.autenticar_admin()
        with CaptureQueriesContext(connection) as consultas:
            resposta = self.client.get(
                self.lista_url, {'page': 2, 'page_size': 18},
            )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['count'], 308)
        self.assertEqual(resposta.data['page_size'], 18)
        self.assertEqual(len(resposta.data['results']), 18)
        self.assertLessEqual(len(consultas), 6, 'Listagem não pode produzir N+1')
        self.assertEqual(
            self.client.get(self.lista_url, {'page_size': 500}).data['page_size'],
            100,
        )
