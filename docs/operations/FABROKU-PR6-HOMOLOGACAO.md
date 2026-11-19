# Panificadora Pires — Homologação PR6 no Fabroku

**Data da preparação:** 19/11/2026.  
**Estado:** branch de deploy preparada, **nenhum aplicativo, serviço, segredo ou domínio criado no Fabroku nesta etapa**.  
**Branch exclusiva:** `deploy/pr6-hml-asgi` baseada em PR6A.2, que incorpora PR6A.1.  
**Produção:** `main`, `dev`, `Procfile` de produção, Vercel público e banco de produção **não são alterados**.

## Alternativa adotada — Neon PostgreSQL externo (limite Fabroku 2/2)

**Decisão de 19/11/2026:** a conta Fabroku já usa sua cota de dois serviços: `backend-pires-db` (PostgreSQL da aplicação principal, **intocável**) e `backend-pires-hml-redis` (Redis exclusivo para a HML, ainda sem vínculo). **Não criar nem tentar reutilizar** um segundo banco no Fabroku; usar PostgreSQL Neon Free, dedicado somente a dados de testes.

### Antes de criar o aplicativo HML

1. Acesse [console.neon.tech](https://console.neon.tech/) e crie um projeto **Free** separado, por exemplo `pires-pr6-hml`, e um banco `pires_hml`. Não importe o banco de produção e não use contas, pedidos, QR ou tokens reais.
2. No painel Neon, abra **Connect**, selecione banco e branch de testes; **desative Connection pooling** para copiar a URL **direct** (sem `-pooler`), porque o `Procfile` executa `manage.py migrate` durante o release. Mantenha os parâmetros SSL gerados pelo Neon, incluindo `sslmode=require` (ou mais estrito). A URL contém usuário/senha: **não cole em chat, issue, commit, .env versionado ou print**.
3. O Django já lê `DATABASE_URL` por `dj_database_url.config()`; **nenhuma mudança de código é necessária**. Na configuração privada da **nova aplicação Fabroku** `backend-pires-hml`, cole a URL somente na variável `DATABASE_URL`.
4. Configure `REALTIME_ENABLED=False` inicialmente; quando o novo app existir, vincule **somente** `backend-pires-hml-redis`. O vínculo costuma injetar `REDIS_URL`; `REALTIME_REDIS_URL` é uma substituição opcional exclusiva de homologação.
5. Primeiro valide `GET /api/health/`, migrations e login com usuários fictícios. **Confirme que o container Fabroku alcança a porta 5432 do Neon** (rede de saída pode bloquear) e que o plano Free cobre o volume necessário. Não habilite WS antes de resolver conectividade.
6. Somente após HTTP/DB/Redis testados, configure `REALTIME_ENABLED=True`, origem WSS exata e frontend Vercel Preview. Nenhum segredo de produção é reutilizado.

**Gate adicional:** não reutilizar `DATABASE_URL` da aplicação principal, não vincular `backend-pires-db` à HML e não importar o `.env` de produção. Em caso de `OperationalError`, parar e verificar conectividade/SSL sem remover ou alterar o banco principal.

## 1. Confirmar capacidade e autorização

No projeto Fabroku da equipe, confirmar **antes de criar**:
- permissão/cota para **nova aplicação** de testes `backend-pires-hml` (a cota de serviços 2/2 não implica, necessariamente, limite de aplicações);
- plugin Dokku `redis` instalado, serviço privado vinculado ao app e versão Redis **6.2+** (GETDEL);
- PostgreSQL **Neon Free externo** de testes independente, URL direta com TLS `sslmode=require`, conectividade de saída porta 5432;
- domínio HTTPS válido e proxy Nginx que faça `Upgrade` para WS e respeite idle timeout >= 300 s;
- capacidade de subir um processo ASGI com Uvicorn e pelo menos duas conexões/instâncias para verificação cross-worker;
- como o Fabroku seleciona branch de origem e processa deploys de branches que não são `main`; **não apontar a app atual para esta branch**.

O [Fabroku Backend](https://github.com/fabricadesoftware-ifc/Fabroku_BackEnd) documenta criação e vínculo de serviços Redis e PostgreSQL via Dokku e template Nginx com `proxy_set_header Upgrade`, mas a configuração da instância do IFC **ainda não foi inspecionada**.

## 2. Provisionar infraestrutura isolada

Na interface Fabroku autorizada, criar **segundo app**, com nome distinto e branch `deploy/pr6-hml-asgi` do repositório `Panificadora-Pires/backend-pires`. Nunca substitua o app `backend-pires` existente.

Usar **PostgreSQL Neon HML externo** por `DATABASE_URL` privada na app HML, sem criar banco local Fabroku devido à cota 2/2; criar/vincular somente o **Redis HML já provisionado**. O vínculo Redis do Fabroku geralmente injeta `REDIS_URL`; o backend aceita `REALTIME_REDIS_URL` com prioridade, senão `REDIS_URL`. **Não expor Redis na internet** nem copiar URLs/segredos para issues, chats, logs, repositórios ou capturas.

Preparar variáveis no próprio Fabroku (valores abaixo são placeholders, jamais credenciais):

```dotenv
DEBUG=False
SECRET_KEY=<GERAR_CHAVE_NOVA_SO_PARA_HML>
ALLOWED_HOSTS=<HOST_BACKEND_HML>
FRONTEND_URLS=https://<HOST_EXATO_PREVIEW_VERCEL>
REALTIME_ALLOWED_ORIGINS=https://<HOST_EXATO_PREVIEW_VERCEL>
REALTIME_ENABLED=False
REALTIME_TICKET_TTL_SECONDS=45
REALTIME_MAX_CONNECTION_SECONDS=300
THROTTLE_REALTIME_TICKET=15/min
# DATABASE_URL: colar URL direta Neon Free SOMENTE no painel privado da nova app HML.
# REDIS_URL: inserida pelo vínculo do serviço backend-pires-hml-redis.
# REALTIME_REDIS_URL é opcional se REDIS_URL estiver configurada.
```

Validar outras variáveis que o sistema exige no `.env.production.example`, usando credenciais e serviços **exclusivos de HML**. Não configurar webhooks do Mercado Pago de produção, secrets reais nem enviar e-mails reais. Testes financeiros apenas com credenciais de sandbox e contas próprias.

**Importante:** CORS HTTP usa `FRONTEND_URLS`; a origem do handshake WS é controlada por `REALTIME_ALLOWED_ORIGINS`. Ambos devem conter apenas domínios exatos do ambiente de teste. Sem `*`.

## 3. Subir ASGI com o WebSocket inicialmente desligado

A branch HML, e somente ela, altera o `Procfile` para:

```procfile
web: sh -c 'exec uvicorn app.asgi:application --host 0.0.0.0 --port "${PORT:-5000}" --ws wsproto'
release: python manage.py migrate --noinput
```

`wsproto` foi adicionado como dependência explícita do Uvicorn. O Dokku deve expor a porta interna conforme o `PORT` ou `5000`; **confirmar no mapeamento da instalação**, pois a configuração do proxy ainda não foi validada.

Ao criar/deployar o app HML:
- verificar logs de build, PDM e migrações **apenas do banco Neon HML**; se houver erro de conexão, verificar saída TCP 5432/SSL;
- verificar `GET https://<HOST_BACKEND_HML>/api/health/` e endpoints HTTP normais;
- validar login de contas de teste sem e-mails reais;
- confirmar que `POST /api/realtime/ticket/` responde **503** com `REALTIME_ENABLED=False`.

Se migrações ou acesso HTTP falharem, **parar** antes de ativar WS. Não tentar corrigir apontando `DATABASE_URL` para produção. O banco Neon pode suspender o compute ocioso e ter atraso na primeira conexão.

## 4. Habilitar realtime na HML

Depois que HTTP e Redis privado estiverem validados, mudar somente na aplicação HML:
```dotenv
REALTIME_ENABLED=True
```
Reiniciar apenas a app HML (o Fabroku pode reiniciar após atualizar a variável). Validar ausência de erro na configuração Redis e `CHANNEL_LAYERS`.

Na preview Vercel separada, configurar em ambiente de **Preview** (não Production):
```dotenv
VITE_REALTIME_ENABLED=true
VITE_API_URL=https://<HOST_BACKEND_HML>/api
```
Gerar novo build preview apontando **somente** para a HML.

## 5. Testes ponta a ponta

1. **Saúde e segurança:** `/api/health/` retorna HTTP OK; ticket recusado a anônimo, permitido a conta ativa; não usar JWT em URL; subprotocol `pires.v1` e ticket one-time, sem replay, expira após 45 s.
2. **Proxy:** DevTools → Network → WS: handshake `101 Switching Protocols`, URL `wss://`, origem exata, sem bloqueio de certificado; avaliar fechamento após 300 s e nova autenticação.
3. **Isolamento:** entrar como admin e clientes A/B em duas sessões privadas; pedido e mensagem de A **não aparecem em B**; admin vê apenas sinais de invalidação autorizados.
4. **Pedidos:** checkout em dinheiro e sandbox; mudança Kanban/QR; notificação do cliente e atualização dos contadores; nenhum valor, QR, e-mail ou texto chat aparece no payload WS.
5. **Chat:** mensagem dos dois lados, confirmação de leitura, painel aberto e sininho; filtros/paginação e estados mantidos.
6. **Durabilidade:** rollback de transação não gera sinal; reiniciar Redis ou derrubar WS; HTTP continua funcionando e polling entrega os dados; reconectar e comparar snapshot REST.
7. **Cross-worker:** quando autorizado, testar dois processos/instâncias ASGI usando o mesmo Redis privado, contas conectadas a workers distintos; sinal deve atravessar workers.
8. **Regressão:** logout/troca de conta, duas abas, mobile 390px, acessibilidade, pagamentos sandbox, QR, duplicatas e mais de 3 mil pedidos de teste.

Não copiar HAR com cabeçalhos `Sec-WebSocket-Protocol` (o ticket efêmero pode aparecer) nem screenshots de QR real.

## 6. Reversão controlada

Se WS falhar:
1. No frontend **Preview**: desligar `VITE_REALTIME_ENABLED` e refazer build (polling permanece ativo).
2. Na HML: desligar `REALTIME_ENABLED`, reiniciar apenas app HML; confirma-se `/api/health/`.
3. Se ASGI/porta falhar: restaurar Procfile Gunicorn/WSGI **apenas na branch/deploy HML**, redeployar o app HML.
4. Manter Neon/Redis HML isolados para diagnóstico; não reutilizar produção e não fazer merges automáticos.

## 7. Gate da produção

O PR7 só poderá propor `dev` → `main` após validação real documentada, rollback reproduzido, CI e segurança aprovados, e autorização para migração ASGI do serviço de produção. **Nunca alterar o app `backend-pires` de produção como forma de validar este roteiro**.
