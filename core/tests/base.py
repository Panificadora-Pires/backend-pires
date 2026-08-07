import re

from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='Pires Panificadora <teste@example.com>',
    VERIFICATION_CODE_TTL_MINUTES=10,
    VERIFICATION_MAX_ATTEMPTS=5,
    VERIFICATION_RESEND_COOLDOWN_SECONDS=60,
    GOOGLE_CLIENT_ID='google-client-id.apps.googleusercontent.com',
)
class AuthAPITestCase(APITestCase):
    strong_password = 'SenhaForte!2026'

    def setUp(self):
        super().setUp()
        if hasattr(mail, 'outbox'):
            mail.outbox.clear()

    def latest_email_code(self):
        self.assertGreaterEqual(len(mail.outbox), 1)
        match = re.search(r'\b(\d{6})\b', mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1)
