"""Cria contas fictícias isoladas para homologar a HML da Pires.

Somente a branch de deploy HML contém este comando. Não envia e-mails,
não imprime senhas e recusa banco ou domínio fora da homologação Neon.
Execução manual pelo Fabroku: python manage.py preparar_contas_hml
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


HOST_HML = "backend-pires-hml.class.fabricadesoftware.ifc.edu.br"
CONTAS = (
    ("admin.hml@pires.invalid", "Admin HML", "HML_ADMIN_PASSWORD", True),
    ("cliente-a.hml@pires.invalid", "Cliente A HML", "HML_CLIENTE_A_PASSWORD", False),
    ("cliente-b.hml@pires.invalid", "Cliente B HML", "HML_CLIENTE_B_PASSWORD", False),
)


class Command(BaseCommand):
    help = "Cria um admin e dois clientes fictícios somente no PostgreSQL Neon de homologação."

    def handle(self, *args, **options):
        # Falhar fechado: este comando NÃO deve ser reutilizado em produção.
        hosts = [host.lower() for host in settings.ALLOWED_HOSTS]
        db_host = str(settings.DATABASES["default"].get("HOST") or "").lower()
        if HOST_HML not in hosts or not db_host.endswith(".neon.tech"):
            raise CommandError("Ambiente não é a HML Neon esperada. Nenhum usuário foi criado.")
        if os.environ.get("HML_CONTAS_AUTORIZADAS") != "SIM":
            raise CommandError("HML_CONTAS_AUTORIZADAS=SIM é obrigatório. Nenhum usuário foi criado.")

        user_model = get_user_model()
        senhas = []
        for email, name, var_name, _admin in CONTAS:
            password = os.environ.get(var_name, "")
            if len(password) < 20:
                raise CommandError(
                    f"Variável {var_name} ausente ou senha com menos de 20 caracteres."
                )
            try:
                password_validation.validate_password(
                    password, user=user_model(email=email, name=name)
                )
            except ValidationError:
                raise CommandError(f"Senha em {var_name} não atende aos validadores.") from None
            senhas.append(password)

        if len(set(senhas)) != len(senhas):
            raise CommandError("As três senhas devem ser diferentes.")

        with transaction.atomic():
            existentes = list(
                user_model.objects.select_for_update().filter(
                    email__in=[email for email, *_ in CONTAS]
                ).values_list("email", flat=True)
            )
            if existentes:
                raise CommandError(
                    "Já existem contas de homologação. Nenhuma senha foi alterada; "
                    "não execute novamente sem investigar."
                )
            for (email, name, _var_name, admin), senha in zip(CONTAS, senhas):
                user_model.objects.create_user(
                    email=email,
                    password=senha,
                    name=name,
                    email_verified=True,
                    is_active=True,
                    is_staff=admin,
                    is_superuser=admin,
                )

        self.stdout.write(self.style.SUCCESS("Contas HML criadas e verificadas no Neon:"))
        self.stdout.write("  Admin: admin.hml@pires.invalid")
        self.stdout.write("  Cliente A: cliente-a.hml@pires.invalid")
        self.stdout.write("  Cliente B: cliente-b.hml@pires.invalid")
        self.stdout.write("Nenhuma senha foi escrita nos logs. Remova as quatro variáveis HML após o teste.")
