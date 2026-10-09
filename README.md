# Pires Panificadora — Backend

API REST do sistema de pedidos da Pires Panificadora.

O backend é responsável por autenticação, catálogo, favoritos, pedidos, pagamentos, estoque, notificações, retirada por QR Code, relatórios e administração.

## Stack

- Python 3.12
- Django 5.2
- Django REST Framework
- SimpleJWT
- django-filter
- drf-spectacular
- PostgreSQL
- SQLite para desenvolvimento
- Cloudinary
- WhiteNoise
- Gunicorn
- Requests
- Google Auth
- Mercado Pago Orders API
- PDM

## URL de produção

API:

```text
https://backend-pires.class.fabricadesoftware.ifc.edu.br/api
```

Frontend autorizado:

```text
https://frontend-pires.vercel.app
```

## Arquitetura

O projeto é dividido por domínio:

```text
app/            → configuração global do Django
core/           → usuários, autenticação, convites, verificação e permissões
catalogo/       → categorias, produtos e promoções
favoritos/      → produtos favoritados
notificacoes/   → notificações dos usuários
pedidos/        → pedidos, estoque, pagamentos, QR Code e relatórios
scripts/        → scripts auxiliares
```

Nos módulos maiores, models, serializers e views ficam separados em arquivos próprios.

## Desenvolvimento local

### Pré-requisitos

- Python 3.12
- PDM

### Instalação

```bash
pdm install
```

Aplique as migrations:

```bash
pdm run python manage.py migrate
```

Opcionalmente, carregue os dados de exemplo:

```bash
pdm run python manage.py seed_dados
```

Execute o servidor:

```bash
pdm run python manage.py runserver
```

Se o projeto possuir o script `dev` configurado no PDM, também pode ser utilizado:

```bash
pdm dev
```

API local:

```text
http://127.0.0.1:8000/api
```

## Comandos úteis

```bash
pdm run python manage.py check
pdm run python manage.py makemigrations --check
pdm run python manage.py migrate
pdm run python manage.py test
pdm run python manage.py test pedidos
pdm run python manage.py collectstatic --noinput
```

Para popular o banco:

```bash
pdm run python manage.py seed_dados
```

Para limpar e recriar os dados de exemplo, quando suportado pelo comando:

```bash
pdm run python manage.py seed_dados --limpar
```

Para executar o cancelamento de pedidos expirados:

```bash
pdm run python manage.py cancelar_pedidos_expirados
```

## Documentação da API

Quando habilitado no projeto:

```text
/api/doc/       → Swagger UI
/api/schema/    → OpenAPI
/admin/         → Django Admin
```

## Banco de dados

Em desenvolvimento existe fallback para SQLite.

Em produção é utilizado PostgreSQL através de:

```env
DATABASE_URL=
```

## Arquivos e imagens

Em produção, uploads devem ser persistidos através do Cloudinary:

```env
CLOUDINARY_URL=
```

Sem storage persistente, arquivos enviados para o filesystem da instância podem ser perdidos após restart ou redeploy.

## Autenticação

A autenticação utiliza JWT através do SimpleJWT.

O sistema também possui recursos de:

- registro;
- login;
- refresh de token;
- login Google;
- verificação de conta;
- recuperação de senha;
- perfil;
- convites administrativos.

As rotas protegidas utilizam:

```http
Authorization: Bearer <access_token>
```

O sistema diferencia usuários comuns e administração por permissões do backend. Um usuário não deve conseguir promover a própria conta através de endpoint público.

## Catálogo

O módulo `catalogo` é responsável por:

- categorias;
- produtos;
- preços;
- estoque;
- promoções;
- validações de promoção;
- dados utilizados pelo cardápio.

As validações de preço e disponibilidade devem sempre ocorrer no backend.

## Favoritos

O módulo `favoritos` gerencia produtos favoritados pelos usuários.

O frontend possui serviço e store próprios para essa funcionalidade, mas a persistência pertence ao backend.

## Notificações

O módulo `notificacoes` registra avisos destinados aos usuários.

Entre os usos do sistema está a notificação quando um pedido fica pronto para retirada.

## Pedidos

O módulo `pedidos` concentra:

- criação do pedido;
- itens;
- cálculo de total;
- estoque;
- status;
- cancelamento;
- pagamentos;
- Mercado Pago;
- QR Code;
- retirada;
- relatórios.

## Fluxo do pedido

Fluxo principal:

```text
pendente
   ↓
confirmado
   ↓
pronto
   ↓
retirado
```

Cancelamentos podem ocorrer antes da retirada, respeitando as regras de negócio e a conciliação financeira.

O sistema impede transições inválidas entre estados.

## Estoque

A lógica de estoque é tratada no backend.

Entre as regras implementadas:

- baixa de estoque ao criar/reservar um pedido;
- validação de estoque suficiente;
- devolução de estoque em cancelamentos aplicáveis;
- proteção contra alteração indevida pelo frontend.

## Cancelamento automático

Existe o management command:

```bash
python manage.py cancelar_pedidos_expirados
```

Ele trata pedidos que ultrapassam o limite configurado para retirada.

Variável relacionada:

```env
PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS=
```

## QR Code de retirada

Cada pedido possui um código de retirada.

O cliente pode visualizar o QR Code e a administração pode confirmar a retirada por leitura da câmera ou entrada manual.

A retirada só deve ser concluída quando o pedido estiver em estado compatível.

## Pagamentos

O checkout suporta:

- dinheiro na retirada;
- Pix;
- cartão.

Os pagamentos eletrônicos utilizam o Mercado Pago Orders API.

### Responsabilidades

Frontend:

```text
Public Key
Payment Brick
interface do checkout
```

Backend:

```text
Access Token
criação da Order
validação do pagamento
webhook
conciliação
status financeiro
```

Nunca confie em preço ou status financeiro enviados pelo frontend.

## Mercado Pago

Variáveis essenciais:

```env
MERCADO_PAGO_ACCESS_TOKEN=
MERCADO_PAGO_WEBHOOK_SECRET=
MERCADO_PAGO_WEBHOOK_URL=
MERCADO_PAGO_API_BASE_URL=https://api.mercadopago.com
MERCADO_PAGO_TIMEOUT_SECONDS=15
MERCADO_PAGO_SANDBOX=False
PAGAMENTO_TEMPO_LIMITE_MINUTOS=45
```

Em produção:

```env
MERCADO_PAGO_SANDBOX=False
```

A Public Key do frontend e o Access Token do backend devem pertencer à mesma aplicação Mercado Pago.

### Pix em produção

A conta Mercado Pago vinculada à aplicação deve possuir uma chave Pix cadastrada e ativa.

Sem chave Pix, a criação da transação pode falhar mesmo que Access Token, Public Key e Webhook estejam corretos.

## Webhook Mercado Pago

Endpoint:

```text
POST /api/pedidos/mercado_pago_webhook/
```

Evento configurado:

```text
Order (Mercado Pago)
```

URL de produção:

```text
https://backend-pires.class.fabricadesoftware.ifc.edu.br/api/pedidos/mercado_pago_webhook/
```

O webhook deve responder `200` depois de receber e tratar corretamente a notificação.

Um `200` no webhook significa que a notificação foi recebida. Não significa, por si só, que o pagamento foi aprovado. Eventos como `order.failed` também podem ser entregues com sucesso ao webhook.

Em produção, assinaturas HMAC inválidas devem ser rejeitadas.

## Variáveis de ambiente de produção

Exemplo para o Fabroku:

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

Nunca versione valores reais de:

- `SECRET_KEY`;
- `DATABASE_URL`;
- `CLOUDINARY_URL`;
- senha SMTP;
- Access Token;
- Webhook Secret.

## Configuração de produção

O projeto está preparado para operar atrás de proxy HTTPS, incluindo:

- `SECURE_PROXY_SSL_HEADER`;
- cookies seguros quando `DEBUG=False`;
- CORS e CSRF por origem permitida;
- `STATIC_ROOT`;
- WhiteNoise;
- Cloudinary quando configurado;
- banco via `DATABASE_URL`.

## Deploy

Antes do deploy:

```bash
pdm run python manage.py check
pdm run python manage.py makemigrations --check
pdm run python manage.py test
```

Durante o deploy, devem ocorrer as etapas equivalentes a:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn app.wsgi
```

Use os comandos configurados na plataforma quando aplicável.

O repositório também contém:

```text
Procfile
build.sh
runtime.txt
```

para suportar o processo de publicação.

## Preflight

Antes de uma entrega ou nova versão, valide:

```text
Django check
migrations --check
testes automatizados
build do frontend
```

O projeto deve ir para produção somente depois dessas etapas passarem.

## Smoke test de produção

Depois do deploy, valide:

1. API responde em HTTPS;
2. login comum;
3. refresh JWT;
4. login Google;
5. catálogo;
6. promoções;
7. favoritos;
8. upload de imagem;
9. envio de e-mail;
10. criação de pedido;
11. dinheiro na retirada;
12. Pix;
13. cartão;
14. webhook retorna `200`;
15. pedido muda para confirmado após pagamento aprovado;
16. administração altera o pedido para pronto;
17. cliente visualiza QR Code;
18. admin confirma retirada;
19. cancelamento devolve estoque quando aplicável;
20. logs não exibem segredos.

## Fluxo completo de pagamento online

```text
Cliente
  ↓
Frontend
  ↓
Backend
  ↓
Mercado Pago
  ↓
Order / pagamento
  ↓
Webhook
  ↓
Backend valida o evento
  ↓
Pagamento aprovado
  ↓
Pedido confirmado
```

## Fluxo completo de retirada

```text
Pedido confirmado
  ↓
Admin prepara
  ↓
Pronto
  ↓
Cliente recebe QR Code
  ↓
Admin escaneia
  ↓
Retirado
```

## Segurança

Regras essenciais:

- `DEBUG=False` em produção;
- não confiar em preços enviados pelo frontend;
- não confiar em status financeiro enviado pelo frontend;
- não expor Access Token;
- não expor Webhook Secret;
- não logar tokens e segredos;
- restringir `ALLOWED_HOSTS`;
- restringir `FRONTEND_URLS`;
- usar HTTPS;
- armazenar mídia em serviço persistente;
- utilizar PostgreSQL em produção;
- manter backups do banco e da mídia;
- rejeitar assinatura inválida no webhook de produção;
- rotacionar credenciais que tenham sido expostas em logs ou arquivos compartilhados.

## Estado atual

O núcleo funcional está concluído e o sistema possui ambiente de produção configurado.

A aplicação está preparada para operação com:

- frontend na Vercel;
- backend no Fabroku;
- PostgreSQL;
- Cloudinary;
- autenticação JWT e Google;
- Mercado Pago em produção;
- Webhook de Orders;
- Pix;
- cartão;
- retirada por QR Code.

Alterações futuras devem ser submetidas novamente ao preflight e ao smoke test antes de publicação.
