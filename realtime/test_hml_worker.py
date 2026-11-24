"""Somente HML: cabeçalho com o PID do worker para o teste PR7C."""
import os

from django.test import SimpleTestCase
from rest_framework.test import APIClient


class HmlWorkerHeaderTests(SimpleTestCase):
    databases = {'default'}

    def test_resposta_informa_somente_o_pid_do_worker(self):
        resposta = APIClient().get('/api/health/')

        self.assertEqual(resposta['X-HML-Worker'], str(os.getpid()))
