"""O seed cria um admin com senha conhecida e não pode rodar em produção por engano."""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.models import User


class SeedDadosTestCase(TestCase):
    @override_settings(DEBUG=False)
    def test_recusa_rodar_com_debug_desligado(self):
        with self.assertRaises(CommandError):
            call_command('seed_dados')

        assert not User.objects.filter(email='admin@cantina.ifc.edu.br').exists()

    @override_settings(DEBUG=True)
    def test_roda_normalmente_em_desenvolvimento(self):
        call_command('seed_dados', stdout=StringIO())

        assert User.objects.filter(email='admin@cantina.ifc.edu.br').exists()
