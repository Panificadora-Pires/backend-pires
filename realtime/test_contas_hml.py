"""Testes da barreira de segurança de criação de contas HML."""
import os
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from realtime.management.commands.preparar_contas_hml import HOST_HML


CREDENCIAIS = {
    "HML_CONTAS_AUTORIZADAS": "SIM",
    "HML_ADMIN_PASSWORD": "F9#2vHjLm6!qP4rTs8WzK7a",
    "HML_CLIENTE_A_PASSWORD": "K2!zW8pTq6#sV4hRm9YaF3b",
    "HML_CLIENTE_B_PASSWORD": "D7#qM3tYn9!vK5zRp2WsH8c",
}
NEON_HML = {"default": {"HOST": "ep-hml-teste.sa-east-1.aws.neon.tech"}}


class PrepararContasHmlTests(TestCase):
    def test_cria_tres_contas_verificadas_e_nao_exibe_senhas(self):
        saida = StringIO()
        with patch.dict(os.environ, CREDENCIAIS), patch.object(
            settings, "ALLOWED_HOSTS", [HOST_HML]
        ), patch.object(settings, "DATABASES", NEON_HML):
            call_command("preparar_contas_hml", stdout=saida)
        usuarios = get_user_model().objects.order_by("email")
        self.assertEqual(usuarios.count(), 3)
        admin = usuarios.get(email="admin.hml@pires.invalid")
        cliente = usuarios.get(email="cliente-a.hml@pires.invalid")
        self.assertTrue(admin.is_active and admin.email_verified)
        self.assertTrue(admin.is_staff and admin.is_superuser)
        self.assertTrue(admin.check_password(CREDENCIAIS["HML_ADMIN_PASSWORD"]))
        self.assertTrue(cliente.is_active and cliente.email_verified)
        self.assertFalse(cliente.is_staff or cliente.is_superuser)
        self.assertTrue(cliente.check_password(CREDENCIAIS["HML_CLIENTE_A_PASSWORD"]))
        self.assertNotIn(CREDENCIAIS["HML_ADMIN_PASSWORD"], saida.getvalue())
        self.assertNotIn(CREDENCIAIS["HML_CLIENTE_A_PASSWORD"], saida.getvalue())

    def test_recusa_dominio_de_producao(self):
        with patch.dict(os.environ, CREDENCIAIS), patch.object(
            settings, "ALLOWED_HOSTS", ["backend-pires.class.fabricadesoftware.ifc.edu.br"]
        ), patch.object(settings, "DATABASES", NEON_HML):
            with self.assertRaisesMessage(CommandError, "Ambiente não é a HML"):
                call_command("preparar_contas_hml", stdout=StringIO())
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_recusa_postgresql_fora_do_neon(self):
        with patch.dict(os.environ, CREDENCIAIS), patch.object(
            settings, "ALLOWED_HOSTS", [HOST_HML]
        ), patch.object(settings, "DATABASES", {"default": {"HOST": "localhost"}}):
            with self.assertRaisesMessage(CommandError, "Ambiente não é a HML"):
                call_command("preparar_contas_hml", stdout=StringIO())
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_requer_permissao_explicita(self):
        env = {**CREDENCIAIS, "HML_CONTAS_AUTORIZADAS": "NAO"}
        with patch.dict(os.environ, env), patch.object(
            settings, "ALLOWED_HOSTS", [HOST_HML]
        ), patch.object(settings, "DATABASES", NEON_HML):
            with self.assertRaisesMessage(CommandError, "HML_CONTAS_AUTORIZADAS"):
                call_command("preparar_contas_hml", stdout=StringIO())

    def test_impede_reexecucao_sem_resetar_credenciais(self):
        with patch.dict(os.environ, CREDENCIAIS), patch.object(
            settings, "ALLOWED_HOSTS", [HOST_HML]
        ), patch.object(settings, "DATABASES", NEON_HML):
            call_command("preparar_contas_hml", stdout=StringIO())
            with self.assertRaisesMessage(CommandError, "Já existem contas"):
                call_command("preparar_contas_hml", stdout=StringIO())
        self.assertEqual(get_user_model().objects.count(), 3)

    def test_falha_sem_criar_usuarios_se_uma_senha_falta(self):
        env = {**CREDENCIAIS, "HML_CLIENTE_B_PASSWORD": ""}
        with patch.dict(os.environ, env), patch.object(
            settings, "ALLOWED_HOSTS", [HOST_HML]
        ), patch.object(settings, "DATABASES", NEON_HML):
            with self.assertRaisesMessage(CommandError, "HML_CLIENTE_B_PASSWORD"):
                call_command("preparar_contas_hml", stdout=StringIO())
        self.assertEqual(get_user_model().objects.count(), 0)
