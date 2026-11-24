"""Somente HML: gerador de dados sintéticos de escala (gerar_escala_hml)."""
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from catalogo.models import Categoria, Produto, Promocao
from core.models import User
from pedidos.models import ItemPedido, Pedido

COMANDO = 'gerar_escala_hml'
PEQUENO = ['--categorias', '3', '--produtos', '30', '--promocoes', '6', '--usuarios', '12', '--pedidos', '25']


def rodar(*args):
    call_command(COMANDO, *args, stdout=StringIO())


class GerarEscalaHmlTests(TestCase):
    def setUp(self):
        self.categoria_real = Categoria.objects.create(nome='Salgados')
        self.produto_real = Produto.objects.create(
            nome='Coxinha', categoria=self.categoria_real, preco=Decimal('6.00'), estoque=10,
        )
        self.usuario_real = User.objects.create_user(email='real@teste.com', password='senha12345')

    def test_recusa_fora_da_hml_sem_alterar_dados(self):
        with self.assertRaisesMessage(CommandError, 'HML Neon'):
            rodar('--confirmar-hml', *PEQUENO)
        self.assertEqual(Produto.objects.count(), 1)

    @patch('realtime.management.commands.gerar_escala_hml.ambiente_hml', return_value=True)
    def test_exige_confirmacao_explicita(self, _ambiente):
        with self.assertRaisesMessage(CommandError, '--confirmar-hml'):
            rodar(*PEQUENO)
        self.assertEqual(Produto.objects.count(), 1)

    @patch('realtime.management.commands.gerar_escala_hml.ambiente_hml', return_value=True)
    def test_gera_marcado_e_remove_somente_sintetico(self, _ambiente):
        rodar('--confirmar-hml', *PEQUENO)

        self.assertEqual(Categoria.objects.filter(nome__startswith='Escala ').count(), 3)
        self.assertEqual(Produto.objects.filter(codigo__startswith='ESC').count(), 30)
        self.assertEqual(Promocao.objects.count(), 6)
        self.assertEqual(User.objects.filter(email__endswith='@escala.hml.invalid').count(), 12)
        pedidos = Pedido.objects.filter(usuario__email__endswith='@escala.hml.invalid')
        self.assertEqual(pedidos.count(), 25)
        self.assertTrue(ItemPedido.objects.filter(pedido__in=pedidos).exists())
        self.assertFalse(pedidos.filter(status=Pedido.Status.RETIRADO).exclude(
            status_pagamento=Pedido.StatusPagamento.APROVADO).exists())
        self.assertGreater(pedidos.values('data__date').distinct().count(), 1)
        self.assertFalse(User.objects.get(email='cliente00001@escala.hml.invalid').has_usable_password())

        with self.assertRaisesMessage(CommandError, 'Já existem dados de escala'):
            rodar('--confirmar-hml', *PEQUENO)

        rodar('--confirmar-hml', '--remover')

        self.assertFalse(Produto.objects.filter(codigo__startswith='ESC').exists())
        self.assertFalse(Categoria.objects.filter(nome__startswith='Escala ').exists())
        self.assertFalse(User.objects.filter(email__endswith='@escala.hml.invalid').exists())
        self.assertFalse(Promocao.objects.exists())
        self.assertTrue(Produto.objects.filter(pk=self.produto_real.pk).exists())
        self.assertTrue(Categoria.objects.filter(pk=self.categoria_real.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.usuario_real.pk).exists())
