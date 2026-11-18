"""Contrato do resumo administrativo sem carregamento integral de pedidos."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from pedidos.models import Pedido

from .base import CriaUsuariosEProdutosMixin


class ResumoAdminPedidosTestCase(CriaUsuariosEProdutosMixin, APITestCase):
    url = '/api/pedidos/resumo_admin/'

    def setUp(self):
        self.criar_usuarios()

    def test_requer_conta_administrativa(self):
        resposta_anonima = self.client.get(self.url)
        self.assertIn(resposta_anonima.status_code, (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ))

        self.client.force_authenticate(user=self.aluno)
        self.assertEqual(
            self.client.get(self.url).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_totais_independem_de_paginas_e_ignoram_cancelados_no_pagamento(self):
        for situacao, pagamento in [
            (Pedido.Status.PENDENTE, Pedido.StatusPagamento.PENDENTE),
            (Pedido.Status.CONFIRMADO, Pedido.StatusPagamento.PROCESSANDO),
            (Pedido.Status.PRONTO, Pedido.StatusPagamento.APROVADO),
            (Pedido.Status.RETIRADO, Pedido.StatusPagamento.APROVADO),
            (Pedido.Status.CANCELADO, Pedido.StatusPagamento.PENDENTE),
        ]:
            Pedido.objects.create(
                usuario=self.aluno,
                status=situacao,
                status_pagamento=pagamento,
            )

        antigo = Pedido.objects.create(
            usuario=self.aluno,
            status=Pedido.Status.PENDENTE,
            status_pagamento=Pedido.StatusPagamento.PENDENTE,
        )
        Pedido.objects.filter(pk=antigo.pk).update(
            data=timezone.now() - timedelta(days=1),
        )

        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['data_referencia'], timezone.localdate().isoformat())
        self.assertEqual(resposta.data['total'], 6)
        self.assertEqual(resposta.data['pedidos_hoje'], 5)
        self.assertEqual(resposta.data['pendentes'], 2)
        self.assertEqual(resposta.data['confirmados'], 1)
        self.assertEqual(resposta.data['prontos'], 1)
        self.assertEqual(resposta.data['retirados'], 1)
        self.assertEqual(resposta.data['cancelados'], 1)
        self.assertEqual(resposta.data['pagamentos_pendentes'], 3)

    def test_mais_de_3000_pedidos_sem_buscar_paginas(self):
        Pedido.objects.bulk_create(
            [
                Pedido(usuario=self.aluno, status=Pedido.Status.PENDENTE)
                for _ in range(3001)
            ],
            batch_size=250,
        )
        self.client.force_authenticate(user=self.admin)
        resposta = self.client.get(self.url)

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data['total'], 3001)
        self.assertEqual(resposta.data['pendentes'], 3001)
        self.assertEqual(resposta.data['pagamentos_pendentes'], 3001)
