"""Diagnóstico HML da emissão/consumo de ticket WS sem exibir o ticket.

Executar somente no app backend-pires-hml:
  python manage.py diagnosticar_ticket_hml
Não usa dados/usuários reais. Emite ticket para ID inexistente 0 e o consome.
"""
from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from realtime.tickets import TicketUnavailable, consumir_ticket, emitir_ticket


class Command(BaseCommand):
    help = "Valida REALTIME_ENABLED e emissão/consumo de ticket WebSocket no Redis HML."

    def handle(self, *args, **options):
        db_host = str(settings.DATABASES["default"].get("HOST") or "").lower()
        hosts = [str(v).lower() for v in settings.ALLOWED_HOSTS]
        if (
            "backend-pires-hml.class.fabricadesoftware.ifc.edu.br" not in hosts
            or not db_host.endswith(".neon.tech")
        ):
            raise CommandError("Ambiente não é a homologação Neon. Nenhuma operação realizada.")

        self.stdout.write(
            "REALTIME_ENABLED efetivo no processo de comando: "
            + ("True" if settings.REALTIME_ENABLED else "False")
        )
        if not settings.REALTIME_ENABLED:
            raise CommandError("Realtime desativado neste processo. Revise variáveis no Fabroku.")

        # ID 0 não pertence a uma conta válida; o segredo nunca vai para saída/logs.
        usuario_ficticio = SimpleNamespace(pk=0, is_active=True, is_staff=False)
        try:
            ticket = emitir_ticket(usuario_ficticio)
            resultado = consumir_ticket(ticket)
            repeticao = consumir_ticket(ticket)
        except TicketUnavailable as exc:
            # O texto da causa pode conter URLs/senhas: somente o NOME da classe é seguro.
            cause_type = type(exc.__cause__).__name__ if exc.__cause__ else "none"
            raise CommandError(
                f"Emissão/consumo de ticket falhou. Categoria interna: {cause_type}"
            ) from None
        if resultado != (0, "usuario") or repeticao is not None:
            raise CommandError("Ticket não comprovou consumo único.")

        self.stdout.write(self.style.SUCCESS("Emissão de ticket Redis: OK"))
        self.stdout.write(self.style.SUCCESS("Consumo único GETDEL do ticket: OK"))
        self.stdout.write(self.style.SUCCESS("HML: fluxo completo de ticket validado"))
