import hashlib
import hmac

from django.test import SimpleTestCase, override_settings

from pedidos.services.pagamentos import validar_assinatura_webhook


class WebhookAssinaturaCaseTests(SimpleTestCase):
    SECRET = 'segredo-de-teste'
    REQUEST_ID = 'req-123'
    DATA_ID = 'ORDTST01M4F90Q1WDXCNNHFB67ZZHB10'
    TS = '1791510000000'

    def _signature(self, data_id):
        manifest = (
            f'id:{data_id};'
            f'request-id:{self.REQUEST_ID};'
            f'ts:{self.TS};'
        )
        digest = hmac.new(
            self.SECRET.encode('utf-8'),
            manifest.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        return f'ts={self.TS},v1={digest}'

    @override_settings(MERCADO_PAGO_WEBHOOK_SECRET=SECRET)
    def test_preserva_case_do_order_id_no_manifesto(self):
        self.assertTrue(
            validar_assinatura_webhook(
                x_signature=self._signature(self.DATA_ID),
                x_request_id=self.REQUEST_ID,
                data_id=self.DATA_ID,
            )
        )

    @override_settings(MERCADO_PAGO_WEBHOOK_SECRET=SECRET)
    def test_assinatura_legacy_lowercase_valida_id_uppercase(self):
        self.assertTrue(
            validar_assinatura_webhook(
                x_signature=self._signature(self.DATA_ID.lower()),
                x_request_id=self.REQUEST_ID,
                data_id=self.DATA_ID,
            )
        )

    @override_settings(MERCADO_PAGO_WEBHOOK_SECRET=SECRET)
    def test_assinatura_incorreta_continua_rejeitada(self):
        assinatura = self._signature('OUTRO-ID')
        self.assertFalse(
            validar_assinatura_webhook(
                x_signature=assinatura,
                x_request_id=self.REQUEST_ID,
                data_id=self.DATA_ID,
            )
        )
