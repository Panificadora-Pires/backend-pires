# Backend — checklist de produção

## Fabroku

Configure:

```env
DEBUG=False
SECRET_KEY=<SEGREDO_FORTE_E_NOVO>
ALLOWED_HOSTS=backend-pires.class.fabricadesoftware.ifc.edu.br
FRONTEND_URLS=https://frontend-pires.vercel.app

DATABASE_URL=<POSTGRES_PRODUCAO>
CLOUDINARY_URL=<CLOUDINARY_PRODUCAO>

GOOGLE_CLIENT_ID=<CLIENT_ID_WEB>

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=<EMAIL>
EMAIL_HOST_PASSWORD=<SENHA_DE_APP>
EMAIL_USE_TLS=True
EMAIL_TIMEOUT=10
DEFAULT_FROM_EMAIL=Pires Panificadora <EMAIL_VALIDO>

MERCADO_PAGO_ACCESS_TOKEN=<ACCESS_TOKEN_PRODUCAO>
MERCADO_PAGO_WEBHOOK_SECRET=<SECRET_WEBHOOK_PRODUCAO>
MERCADO_PAGO_WEBHOOK_URL=https://backend-pires.class.fabricadesoftware.ifc.edu.br/api/pedidos/mercado_pago_webhook/
MERCADO_PAGO_API_BASE_URL=https://api.mercadopago.com
MERCADO_PAGO_TIMEOUT_SECONDS=15
MERCADO_PAGO_SANDBOX=False
PAGAMENTO_TEMPO_LIMITE_MINUTOS=45

PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS=15
VERIFICATION_CODE_TTL_MINUTES=10
VERIFICATION_MAX_ATTEMPTS=5
VERIFICATION_RESEND_COOLDOWN_SECONDS=60
```

## Antes do deploy

```powershell
pdm run python manage.py check
pdm run python manage.py makemigrations --check
pdm run python manage.py test
```

## Durante o deploy

Garanta:

```text
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn app.wsgi
```

Use os comandos já configurados na plataforma quando aplicável.

## Depois do deploy

Validar:
1. API responde por HTTPS.
2. login funciona.
3. refresh JWT funciona.
4. catálogo carrega.
5. upload de imagem permanece após restart.
6. e-mail chega.
7. Webhook produtivo simulado retorna 200.
8. logs não exibem segredos.

Não execute pagamento real antes do item 7.
