"""Redefine senhas das tres contas ficticias, exclusivamente na HML Neon.

Nao recria contas, nao altera permissoes nem imprime credenciais.
Uso na aplicacao Fabroku backend-pires-hml:
    python manage.py redefinir_senhas_hml
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


HOST_HML = "backend-pires-hml.class.fabricadesoftware.ifc.edu.br"
CONTAS = (
    ("admin.hml@pires.invalid", "HML_NOVA_SENHA_ADMIN"),
    ("cliente-a.hml@pires.invalid", "HML_NOVA_SENHA_CLIENTE_A"),
    ("cliente-b.hml@pires.invalid", "HML_NOVA_SENHA_CLIENTE_B"),
)


class Command(BaseCommand):
    help = "Redefine apenas as tres senhas ficticias da HML Neon, sem tocar no banco de producao."

    def handle(self, *args, **options):
        # Nao executar na producao, em SQLite local, ou sem consentimento explicito.
        hosts = {host.lower() for host in settings.ALLOWED_HOSTS}
        db_host = str(settings.DATABASES["default"].get("HOST") or "").lower()
        if HOST_HML not in hosts or not db_host.endswith(".neon.tech"):
            raise CommandError("Ambiente nao e a HML Neon esperada. Nenhuma senha alterada.")
        if os.environ.get("HML_REDEFINICAO_AUTORIZADA") != "SIM":
            raise CommandError("HML_REDEFINICAO_AUTORIZADA=SIM e obrigatorio.")

        senhas = {}
        for email, var_name in CONTAS:
            senha = os.environ.get(var_name, "")
            if len(senha) < 20:
                raise CommandError(f"{var_name} ausente ou tem menos de 20 caracteres.")
            senhas[email] = senha

        if len(set(senhas.values())) != len(CONTAS):
            raise CommandError("As tres novas senhas devem ser diferentes.")

        user_model = get_user_model()
        emails = [email for email, _ in CONTAS]

        # Tudo ou nada: se faltar conta ou houver senha invalida, nao alterar nenhuma.
        with transaction.atomic():
            usuarios = {
                u.email: u
                for u in user_model.objects.select_for_update().filter(email__in=emails)
            }
            if set(usuarios) != set(emails):
                raise CommandError("Uma ou mais contas HML nao existem. Nenhuma senha alterada.")

            for email in emails:
                try:
                    password_validation.validate_password(
                        senhas[email], user=usuarios[email]
                    )
                except ValidationError:
                    raise CommandError(
                        "Uma nova senha nao atende aos validadores. Nenhuma senha alterada."
                    ) from None

            for email in emails:
                usuario = usuarios[email]
                usuario.set_password(senhas[email])
                usuario.save(update_fields=["password"])

        self.stdout.write(self.style.SUCCESS("Tres senhas HML redefinidas com sucesso."))
        self.stdout.write(
            "Teste os logins e remova as quatro variaveis temporarias da HML."
        )
