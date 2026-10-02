"""Testes da assinatura do Mercado Pago usando dados sintéticos."""

import hashlib
import hmac

from django.test import SimpleTestCase, override_settings

from pedidos.services.pagamentos import validar_assinatura_webhook


@override_settings(MERCADO_PAGO_WEBHOOK_SECRET='chave-ficticia-de-teste')
class AssinaturaWebhookTests(SimpleTestCase):
    @staticmethod
    def assinar(*, data_id=None, request_id=None, timestamp='1770000000000'):
        partes = []
        if data_id:
            partes.append(f'id:{data_id.lower()};')
        if request_id:
            partes.append(f'request-id:{request_id};')
        partes.append(f'ts:{timestamp};')
        assinatura = hmac.new(
            b'chave-ficticia-de-teste',
            ''.join(partes).encode(),
            hashlib.sha256,
        ).hexdigest()
        return f'ts={timestamp},v1={assinatura}'

    def test_assinatura_correta_com_order_maiuscula(self):
        assinatura = self.assinar(data_id='ORDTESTABC123', request_id='req-ficticio')
        self.assertTrue(validar_assinatura_webhook(
            x_signature=assinatura,
            x_request_id='req-ficticio',
            data_id='ORDTESTABC123',
        ))

    def test_assinatura_invalida_rejeitada(self):
        assinatura = self.assinar(data_id='ORDTESTABC123', request_id='req-ficticio')
        self.assertFalse(validar_assinatura_webhook(
            x_signature=assinatura,
            x_request_id='req-alterado',
            data_id='ORDTESTABC123',
        ))

    def test_sem_id_na_url_manifesto_omite_id(self):
        assinatura = self.assinar(data_id=None, request_id='req-ficticio')
        self.assertTrue(validar_assinatura_webhook(
            x_signature=assinatura,
            x_request_id='req-ficticio',
            data_id=None,
        ))

    @override_settings(MERCADO_PAGO_WEBHOOK_SECRET='')
    def test_secret_ausente_nao_valida(self):
        assinatura = self.assinar(data_id='ORDTESTABC123', request_id='req-ficticio')
        self.assertFalse(validar_assinatura_webhook(
            x_signature=assinatura,
            x_request_id='req-ficticio',
            data_id='ORDTESTABC123',
        ))
