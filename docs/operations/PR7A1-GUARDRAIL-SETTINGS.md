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

**Nenhum valor secreto foi criado ou modificado no Fabroku.**
