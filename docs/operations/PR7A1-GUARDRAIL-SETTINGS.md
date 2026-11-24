# PR7A.1 — Guardrail de inicialização do backend

Esta alteração **não foi aplicada ao Fabroku**. O destino é apenas `dev` após revisão.

## Regras propostas

- O padrão de `DEBUG` passa a ser `False` em instalações sem `.env`.
- Desenvolvimento permanece com `DEBUG=True` e SQLite conforme `.env.example`.
- Com `DEBUG=False`, o backend **recusa inicializar** se `DATABASE_URL` estiver ausente ou não apontar para `postgres://` / `postgresql://`.
- O `SECRET_KEY` continua obrigatório quando `DEBUG=False`, conforme a proteção já existente.
- Nada muda em migrations, models, endpoints, Redis, Mercado Pago ou regras financeiras.

## Validação automatizada

- `core.tests.test_deploy_guard`: 6 casos, sem acesso a nenhum DB.
- CI completa: testes Django normais com SQLite fictício e `DEBUG=True`.
- CI extra: `python manage.py check --deploy` com `DEBUG=False`, URL de PostgreSQL **fictícia** e sem chamadas ao banco.
- Avisos de HSTS e SSL no `check --deploy` são inventariados como pendência de proxy/infraestrutura; a execução não é certificação de segurança.

## Homologação antes da produção

1. Conferir apenas presença/tipo de `DATABASE_URL` PostgreSQL na HML e produção (sem copiar senha nem valor).
2. Confirmar `DEBUG=False` no ambiente real e quais headers `X-Forwarded-Proto` chegam pelo proxy.
3. Testar startup na HML com PostgreSQL e modo não-debug antes de aplicar este guardrail ao release.
4. O PR deve ser integrado à `dev` apenas após revisão e CI. A ativação na `main`, o deploy e ASGI/Redis permanecem bloqueados até o gate #62.

## Evidências coletadas em 23/11/2026

Somente leitura, sem autenticação e sem acesso a valores de variáveis.

| Verificação | HML (`backend-pires-hml`) | Produção (`backend-pires`) |
| --- | --- | --- |
| `GET http://…/api/health/` | `301` para `https://` (nginx) | `301` para `https://` (nginx) |
| `GET https://…/api/health/` | `200 {"status":"ok"}` | `200 {"status":"ok"}` |
| Cabeçalho HSTS enviado pelo proxy | `max-age=15724800; includeSubdomains` | `max-age=15724800; includeSubdomains` |
| `DEBUG` efetivo (rota inexistente) | 404 genérico, sem página técnica do Django | 404 genérico, sem página técnica do Django |
| Presença de `DEBUG`, `SECRET_KEY`, `DATABASE_URL` no painel | Confirmada pelo responsável (print, valores ocultos) | `DATABASE_URL` confirmada pelo responsável |

### Classificação dos 18 avisos do `check --deploy` (env sintética)

- **15 `drf_spectacular.W001` + 1 `W002`**: qualidade do schema OpenAPI (type hints em `get_*`, parâmetros de rota sem tipo, `get_queryset` dependente de `request.user`, `ChatbotViewSet` sem serializer). Sem impacto de segurança: a documentação fica desligada em produção (`ENABLE_API_DOCS=False`). Correção opcional em PR próprio.
- **`security.W004` (HSTS) e `security.W008` (SSL redirect)**: cobertos pelo proxy nginx nos dois ambientes (redirect 301 e HSTS acima). Manter `SECURE_SSL_REDIRECT=False` e `SECURE_HSTS_SECONDS=0` no Django evita redirecionamento duplicado; não silenciar os avisos no código, para que voltem a aparecer se o proxy mudar.

### Pendências restantes

- Não é possível comprovar de fora se o proxy sobrescreve um `X-Forwarded-Proto` enviado pelo cliente (R-04 residual).
- O guard também roda no `collectstatic` do `build.sh` e no `release: migrate`. Antes do release (PR7D), confirmar que o Fabroku de produção expõe `DATABASE_URL` também na etapa de build; se não expuser, o deploy falha de forma segura e a versão anterior permanece no ar.
- Validação local em 23/11/2026: 276 testes, `check`, `makemigrations --check` e cenários de recusa (sem `DATABASE_URL`, SQLite com `DEBUG=False`, sem `SECRET_KEY`) conferidos.

**Nenhum valor secreto foi criado ou modificado no Fabroku.**
