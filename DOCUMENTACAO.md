# Backend — Pires Panificadora

API Django/DRF responsável por autenticação, catálogo, pedidos, pagamentos, estoque, retirada e administração.

## Stack

- Python 3.12
- Django 5.2
- Django REST Framework
- SimpleJWT
- django-filter
- drf-spectacular
- PostgreSQL
- Cloudinary
- WhiteNoise
- Gunicorn
- Requests
- Google Auth
- Mercado Pago Orders API

## Desenvolvimento

```powershell
pdm install
pdm run python manage.py migrate
pdm dev
```

API local:
`http://127.0.0.1:8000/api`

## Comandos úteis

```powershell
pdm run python manage.py check
pdm run python manage.py makemigrations --check
pdm run python manage.py migrate
pdm run python manage.py test
pdm run python manage.py test pedidos
pdm run python manage.py collectstatic --noinput
```

## Configuração

Use `.env` local ou variáveis do provedor. Nunca commite segredos.

Veja `.env.production.example` para a lista de variáveis produtivas.

## Produção

O projeto já está preparado para operar atrás de proxy HTTPS:
- `SECURE_PROXY_SSL_HEADER`;
- cookies seguros quando `DEBUG=False`;
- CORS e CSRF controlados por `FRONTEND_URLS`;
- `STATIC_ROOT`;
- WhiteNoise;
- storage Cloudinary quando configurado;
- banco via `DATABASE_URL`.

### Banco
Em desenvolvimento, o fallback é SQLite.
Em produção, informe PostgreSQL em `DATABASE_URL`.

### Arquivos
`CLOUDINARY_URL` deve estar configurado em produção para persistir uploads.

### Autenticação
JWT com rotação e blacklist de refresh tokens.

### Mercado Pago
O checkout online usa Orders API.

Variáveis essenciais:
- `MERCADO_PAGO_ACCESS_TOKEN`
- `MERCADO_PAGO_WEBHOOK_SECRET`
- `MERCADO_PAGO_WEBHOOK_URL`
- `MERCADO_PAGO_TIMEOUT_SECONDS`
- `MERCADO_PAGO_SANDBOX`
- `PAGAMENTO_TEMPO_LIMITE_MINUTOS`

Em produção use `MERCADO_PAGO_SANDBOX=False`.

### Webhook
Endpoint:

`POST /api/pedidos/mercado_pago_webhook/`

Evento:
`Order (Mercado Pago)`

Em produção, assinatura HMAC inválida deve continuar sendo rejeitada.

## Fluxo do pedido

`pendente -> confirmado -> pronto -> retirado`

Cancelamentos podem ocorrer antes da retirada, respeitando a conciliação financeira.

## QR Code

O cliente recebe um código de retirada e o admin pode confirmar a retirada via QR/manual.

## Segurança

- não confiar em preços enviados pelo frontend;
- não confiar em status financeiro enviado pelo frontend;
- não logar tokens/secrets;
- manter `DEBUG=False`;
- restringir `ALLOWED_HOSTS`;
- restringir `FRONTEND_URLS`;
- usar HTTPS;
- manter banco e mídia com backup.
