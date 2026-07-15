"""Testes da RN06 — cancelamento automático de pedidos prontos expirados."""

from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from pedidos.models import ItemPedido, Pedido

from .base import CriaUsuariosEProdutosMixin


class CancelarPedidosExpiradosTestCase(CriaUsuariosEProdutosMixin, TestCase):
    def setUp(self):
        self.criar_usuarios()
        self.criar_produtos()

    def _criar_pedido_pronto_ha(self, minutos, quantidade=2):
        pedido = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.PRONTO)
        ItemPedido.objects.create(
            pedido=pedido, produto=self.coxinha, quantidade=quantidade, preco_unitario=self.coxinha.preco
        )
        self.coxinha.estoque -= quantidade
        self.coxinha.save(update_fields=['estoque'])
        Pedido.objects.filter(pk=pedido.pk).update(status_atualizado_em=timezone.now() - timedelta(minutes=minutos))
        return pedido

    def test_cancela_pedido_expirado(self):
        pedido = self._criar_pedido_pronto_ha(20)
        call_command('cancelar_pedidos_expirados')

        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.CANCELADO

    def test_nao_cancela_pedido_dentro_do_prazo(self):
        pedido = self._criar_pedido_pronto_ha(5)
        call_command('cancelar_pedidos_expirados')

        pedido.refresh_from_db()
        assert pedido.status == Pedido.Status.PRONTO

    def test_devolve_estoque_ao_cancelar(self):
        """Estoque cai na criação (simulada no helper) e deve voltar ao valor original após o cancelamento."""
        estoque_antes = self.coxinha.estoque
        self._criar_pedido_pronto_ha(30, quantidade=2)
        call_command('cancelar_pedidos_expirados')

        self.coxinha.refresh_from_db()
        assert self.coxinha.estoque == estoque_antes

    def test_nao_mexe_em_pedidos_de_outros_status(self):
        pendente = Pedido.objects.create(usuario=self.aluno, status=Pedido.Status.PENDENTE)
        Pedido.objects.filter(pk=pendente.pk).update(status_atualizado_em=timezone.now() - timedelta(hours=5))

        call_command('cancelar_pedidos_expirados')

        pendente.refresh_from_db()
        assert pendente.status == Pedido.Status.PENDENTE
