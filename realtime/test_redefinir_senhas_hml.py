"""Regressoes do reset manual de senhas ficticias na HML."""
import os
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from realtime.management.commands.redefinir_senhas_hml import HOST_HML


ENV_TESTE = {
    "HML_REDEFINICAO_AUTORIZADA": "SIM",
    "HML_NOVA_SENHA_ADMIN": "Hml#Adm7Zq!29Prv6GtW4xLf",
    "HML_NOVA_SENHA_CLIENTE_A": "Hml#Cli8Yp!46Lkw3SdR9mQa",
    "HML_NOVA_SENHA_CLIENTE_B": "Hml#Cli5Tf!83Bnr7VcQ2jWe",
}
NEON = {"default": {"HOST": "ep-hml-teste.sa-east-1.aws.neon.tech"}}
EMAILS = (
    "admin.hml@pires.invalid",
    "cliente-a.hml@pires.invalid",
    "cliente-b.hml@pires.invalid",
)


class RedefinirSenhasHmlTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        for n, email in enumerate(EMAILS):
            admin = n == 0
            self.user_model.objects.create_user(
                email=email,
                name=["Admin HML", "Cliente A HML", "Cliente B HML"][n],
                password=f"SenhaAntiga#Segura{n}98274",
                email_verified=True,
                is_active=True,
                is_staff=admin,
                is_superuser=admin,
            )

    def executar(self, env=None, hosts=None, databases=None):
        with (
            patch.dict(os.environ, env if env is not None else ENV_TESTE, clear=False),
            patch.object(settings, "ALLOWED_HOSTS", hosts if hosts is not None else [HOST_HML]),
            patch.object(settings, "DATABASES", databases if databases is not None else NEON),
        ):
            return call_command("redefinir_senhas_hml", stdout=StringIO())

    def conferir_senhas_antigas(self):
        for n, email in enumerate(EMAILS):
            u = self.user_model.objects.get(email=email)
            self.assertTrue(u.check_password(f"SenhaAntiga#Segura{n}98274"))

    def test_redefine_tres_senhas_sem_modificar_contas_ou_permissoes(self):
        originais = {
            u.email: (u.pk, u.name, u.is_staff, u.is_superuser, u.email_verified, u.is_active)
            for u in self.user_model.objects.all()
        }
        with (
            patch.dict(os.environ, ENV_TESTE, clear=False),
            patch.object(settings, "ALLOWED_HOSTS", [HOST_HML]),
            patch.object(settings, "DATABASES", NEON),
        ):
            saida = StringIO()
            call_command("redefinir_senhas_hml", stdout=saida)

        for email, variavel in zip(
            EMAILS,
            ("HML_NOVA_SENHA_ADMIN", "HML_NOVA_SENHA_CLIENTE_A", "HML_NOVA_SENHA_CLIENTE_B"),
        ):
            u = self.user_model.objects.get(email=email)
            self.assertTrue(u.check_password(ENV_TESTE[variavel]))
            self.assertEqual(
                (u.pk, u.name, u.is_staff, u.is_superuser, u.email_verified, u.is_active),
                originais[email],
            )
            self.assertNotIn(ENV_TESTE[variavel], saida.getvalue())
        self.assertEqual(self.user_model.objects.count(), 3)

    def test_bloqueia_producao(self):
        with self.assertRaisesMessage(CommandError, "Ambiente nao e a HML"):
            self.executar(hosts=["backend-pires.class.fabricadesoftware.ifc.edu.br"])
        self.conferir_senhas_antigas()

    def test_bloqueia_banco_nao_neon(self):
        with self.assertRaisesMessage(CommandError, "Ambiente nao e a HML"):
            self.executar(databases={"default": {"HOST": "localhost"}})
        self.conferir_senhas_antigas()

    def test_exige_autorizacao_temporaria(self):
        env = {**ENV_TESTE, "HML_REDEFINICAO_AUTORIZADA": "NAO"}
        with self.assertRaisesMessage(CommandError, "HML_REDEFINICAO_AUTORIZADA"):
            self.executar(env=env)
        self.conferir_senhas_antigas()

    def test_conta_ausente_nao_altera_as_demais(self):
        self.user_model.objects.filter(email=EMAILS[2]).delete()
        with self.assertRaisesMessage(CommandError, "nao existem"):
            self.executar()
        for n, email in enumerate(EMAILS[:2]):
            self.assertTrue(
                self.user_model.objects.get(email=email).check_password(
                    f"SenhaAntiga#Segura{n}98274"
                )
            )

    def test_nao_aceita_senha_curta(self):
        env = {**ENV_TESTE, "HML_NOVA_SENHA_CLIENTE_B": "curta"}
        with self.assertRaisesMessage(CommandError, "menos de 20"):
            self.executar(env=env)
        self.conferir_senhas_antigas()

    def test_nao_aceita_senhas_iguais(self):
        env = {
            **ENV_TESTE,
            "HML_NOVA_SENHA_CLIENTE_B": ENV_TESTE["HML_NOVA_SENHA_CLIENTE_A"],
        }
        with self.assertRaisesMessage(CommandError, "diferentes"):
            self.executar(env=env)
        self.conferir_senhas_antigas()
