# PR6A.1 — Executar e validar Channels sem alterar produção

**Estado:** implementação experimental, feature flag desligada; `Procfile` do Fabroku ainda usa WSGI.  
**Objetivo:** preparar ASGI, autorização por ticket temporário e camadas Redis para homologação.

## Uso local (PowerShell 5.1 / Windows)

Na worktree isolada `backend-channels-pr6a1`:

```powershell
pdm sync
pdm run python manage.py check
pdm run python manage.py makemigrations --check --dry-run
pdm run python manage.py test realtime --noinput --verbosity 2
```

Para testar somente HTTP, mantenha `REALTIME_ENABLED=False`. Isso preserva o servidor atual e todas as APIs.

Para testar WS, instale um Redis **local e privado**, com suporte a `GETDEL` (Redis >= 6.2). O deploy no Fabroku ainda não foi validado. Em `.env` local, configure:

```dotenv
REALTIME_ENABLED=True
REALTIME_REDIS_URL=redis://localhost:6379/1
REALTIME_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
REALTIME_TICKET_TTL_SECONDS=45
REALTIME_MAX_CONNECTION_SECONDS=300
```

Nunca publique Redis local na internet nem inclua credenciais no repositório. Se Redis não estiver disponível, mantenha o flag desligado. Para subir o **ASGI** explicitamente em ambiente local:

```powershell
pdm run uvicorn app.asgi:application --host 127.0.0.1 --port 8000 --ws wsproto
```

**Atenção:** `pdm run python manage.py runserver` não comprova WebSockets, pois a escolha de servidor deve ser ASGI. O `Procfile` de produção permanece `gunicorn app.wsgi:application` nesta etapa.

## Protocolo de autenticação

1. O frontend usa seu JWT de acesso normal **somente** na chamada autenticada `POST /api/realtime/ticket/`.
2. A API responde `ticket` (45 s), `protocol=pires.v1` e `ws_path=/ws/v1/events/` com `Cache-Control: no-store`.
3. O navegador abre `wss://<backend>/ws/v1/events/` (ou `ws://localhost:8000/ws/v1/events/` **só no desenvolvimento**) com os subprotocolos `pires.v1` e `pires.ticket.<ticket>`.
4. O backend verifica origem, consome o ticket no Redis via `GETDEL` atômico e busca a conta ativa. Admin ingressa no grupo operacional; cliente ingressa somente no próprio grupo.
5. A conexão é **somente leitura**, com duração máxima de 300 s por padrão. O cliente precisará solicitar outro ticket ao reconectar. O PR6B adicionará esse comportamento; enquanto isso o polling existente permanece ativo.
6. Se o Redis cair, o ticket expirar ou a origem/role estiver incorreto, o WS falha fechado. Nenhum comando de pedido, chat ou pagamento passa pelo WS.

Não colocar JWT persistente ou refresh token na URL, nos subprotocolos ou em logs. O subprotocolo carrega **somente ticket efêmero**; o handshake devolve o protocolo fixo `pires.v1`.

## Restrições e próximos gates

- Nenhum evento é produzido automaticamente neste PR: essa integração com `transaction.on_commit` é o PR6A.2.
- Não há ainda validação em dois processos, Redis do Fabroku, proxy `Upgrade`/WSS nem detecção de perda de conexão no Vue.
- Não habilitar `REALTIME_ENABLED` no deploy WSGI atual: o endpoint de ticket passaria a existir, mas conexões WS não seriam atendidas pelo processo.
- A conta é revalidada no **handshake**; a duração limitada de WS reduz o período de permissões obsoletas. Revogação imediata de todas as conexões no logout requer trabalho complementar do PR6/PR7.
- O PR6B deve manter polling como fallback e invalidar dados por eventos, não armazenar dados de pedidos recebidos via WS.
- Validar com admin e cliente distintos, duas sessões, WSS real, ausência de fuga de dados, revogação, impacto no checkout/QR, reinício do Redis e rollback para WSGI antes de publicar.

Links: [Issue backend #56](https://github.com/Panificadora-Pires/backend-pires/issues/56), [PR de arquitetura #57](https://github.com/Panificadora-Pires/backend-pires/pull/57), [Issue frontend #73](https://github.com/Panificadora-Pires/frontend-pires/issues/73).


O driver WebSocket `wsproto` é uma dependência de runtime explícita para Uvicorn; o pacote base `uvicorn` sozinho não garante suporte WS. Em staging Fabroku, ao vincular Redis pelo serviço da plataforma, a URL normalmente é exposta como `REDIS_URL`. `REALTIME_REDIS_URL` opcional tem prioridade se houver Redis dedicado; nunca copie segredos para o Git.
