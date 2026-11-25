# Pires Panificadora — Backend

API REST do sistema de pedidos antecipados da Pires Panificadora, Projeto Integrador do Curso Técnico em Informática do IFC — Campus Araquari. Ela cuida de contas e autenticação, catálogo, pedidos, estoque, pagamentos pelo Mercado Pago, retirada por QR Code, chat por pedido, assistente de dúvidas, notificações, favoritos e relatórios.

- Documentação do projeto: [Panificadora-Pires](https://github.com/Panificadora-Pires/.github)
- Frontend: [frontend-pires](https://github.com/Panificadora-Pires/frontend-pires) e [publicação](https://panificadora-pires.vercel.app)
- API publicada: https://backend-pires.class.fabricadesoftware.ifc.edu.br/api/

O projeto Django se chama `app` e está dividido em aplicações por domínio:

- `core`: usuário customizado (login por e-mail), confirmação de e-mail, redefinição de senha, login com o Google e convites de administrador.
- `catalogo`: categorias, produtos e promoções.
- `pedidos`: pedidos, reserva de estoque, pagamentos (Mercado Pago), retirada por QR Code, cancelamento automático e relatórios.
- `favoritos`, `notificacoes`, `chat` (conversa por pedido) e `chatbot` (perguntas frequentes).
- `realtime`: atualização em tempo real por WebSocket (Django Channels e Redis), opcional.

A regra de negócio fica em `services/` de cada aplicação. As aplicações conversam por sinais (`signals`), sem importar umas às outras.

## Instalação e Configuração

1. Tenha o [Python 3.12](https://www.python.org/) e o [PDM](https://pdm-project.org/) instalados.

2. Clone o repositório e entre na pasta:

   ```
   git clone https://github.com/Panificadora-Pires/backend-pires.git
   cd backend-pires
   ```

3. Instale as dependências:

   ```
   pdm install
   ```

4. Crie o arquivo `.env` a partir do `.env.example`. Ele já vem pronto para desenvolvimento, com SQLite e `DEBUG=True`:

   ```
   cp .env.example .env
   ```

5. Crie o banco e, se quiser, carregue dados fictícios de exemplo (um administrador e três clientes, com produtos e pedidos):

   ```
   pdm run migrate
   pdm run seed_dados
   ```

6. Execute o servidor de desenvolvimento:

   ```
   pdm run dev
   ```

7. Acesse a API em http://127.0.0.1:8000/api/ e confira se ela está no ar em http://127.0.0.1:8000/api/health/.

Para pagar com Pix ou cartão no ambiente local, preencha no `.env` as credenciais de teste do Mercado Pago (`MERCADO_PAGO_ACCESS_TOKEN` e `MERCADO_PAGO_SANDBOX=True`). O pagamento em dinheiro funciona sem configuração extra.

## Uso da API

Com `ENABLE_API_DOCS=True` (padrão do `.env.example`), a documentação completa dos endpoints fica disponível em:

- Swagger: http://127.0.0.1:8000/api/doc/
- ReDoc: http://127.0.0.1:8000/api/redoc/
- Esquema OpenAPI: http://127.0.0.1:8000/api/schema/

Na produção a documentação fica desligada.

A autenticação usa JWT: `POST /api/token/` devolve o `access` e o `refresh`, e o `access` vai no cabeçalho `Authorization: Bearer <access>`. Por padrão, toda rota exige login; as rotas públicas (cadastro, login, confirmação de e-mail, Google, webhook do Mercado Pago e `health`) são declaradas de propósito. O cliente vê apenas os próprios dados, e o administrador (`is_staff`) vê tudo.

## Comandos Úteis

- `pdm run dev`: executa o servidor de desenvolvimento em http://127.0.0.1:8000.
- `pdm run migrate` e `pdm run makemigrations`: aplicam e criam as migrações.
- `pdm run seed_dados`: cria dados fictícios de exemplo (só roda com `DEBUG=True`).
- `pdm run createsuperuser`: cria um administrador.
- `pdm run test`: executa os testes.
- `pdm run django_check`: verifica a configuração do Django.
- `pdm run lint` e `pdm run format`: verificam e formatam o código com o Ruff.
- `pdm run shellp`: abre o shell do Django com todos os modelos importados.
- `pdm run python manage.py cancelar_pedidos_expirados`: cancela os pedidos vencidos. Na produção, um workflow do GitHub chama o endpoint de manutenção a cada 10 minutos.
- Para mais detalhes, veja a seção `[tool.pdm.scripts]` do `pyproject.toml`.

## Testes

Antes de abrir um pull request, rode:

```
pdm run python manage.py test
pdm run python manage.py check
pdm run python manage.py makemigrations --check --dry-run
pdm run ruff check .
```

A integração contínua (`.github/workflows/ci.yml`) executa as mesmas verificações a cada pull request. Os testes não usam serviços externos: Mercado Pago, Google e e-mail são simulados.

## Publicação

O backend é publicado no Fabroku (IFC) a partir da branch `main`. O `Procfile` aplica as migrações a cada publicação e sobe o servidor ASGI (Uvicorn com 2 workers). As variáveis de produção estão descritas em `.env.production.example`; os valores reais são configurados no painel do Fabroku e nunca vão para o repositório.

## Detalhes do Projeto

Esse projeto utiliza os seguintes pacotes e tecnologias:

- [PDM](https://pdm-project.org/): gerenciador de pacotes e ambiente virtual.
- [Django 5.2](https://www.djangoproject.com/) e [Django REST Framework](https://www.django-rest-framework.org/): framework web e de APIs REST.
- [Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/): autenticação JWT, com lista de bloqueio para tokens revogados.
- [django-filter](https://django-filter.readthedocs.io/): filtros nas listagens.
- [drf-spectacular](https://drf-spectacular.readthedocs.io/): documentação OpenAPI (Swagger e ReDoc).
- [PostgreSQL](https://www.postgresql.org/) em produção e [SQLite](https://www.sqlite.org/) em desenvolvimento, configurados por [dj-database-url](https://pypi.org/project/dj-database-url/).
- [Cloudinary](https://cloudinary.com/): armazenamento das imagens dos produtos e das fotos de perfil.
- [Mercado Pago](https://www.mercadopago.com.br/developers): pagamentos por Pix e cartão (Orders API), com webhook validado por assinatura.
- [google-auth](https://pypi.org/project/google-auth/): login com a conta Google.
- [Django Channels](https://channels.readthedocs.io/), [channels-redis](https://pypi.org/project/channels-redis/) e [Uvicorn](https://www.uvicorn.org/): servidor ASGI e atualização em tempo real.
- [qrcode](https://pypi.org/project/qrcode/): geração do QR Code de retirada.
- [django-cors-headers](https://pypi.org/project/django-cors-headers/), [WhiteNoise](https://whitenoise.readthedocs.io/), [requests](https://pypi.org/project/requests/) e [python-dotenv](https://pypi.org/project/python-dotenv/).
- [Ruff](https://docs.astral.sh/ruff/): linter e formatador.

## Licença

Este projeto está licenciado sob a licença MIT, conforme o `pyproject.toml`.
