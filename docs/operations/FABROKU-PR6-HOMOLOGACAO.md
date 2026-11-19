# Panificadora Pires — Homologação PR6 no Fabroku

**Data da preparação:** 19/11/2026.  
**Estado:** branch de deploy preparada, **nenhum aplicativo, serviço, segredo ou domínio criado no Fabroku nesta etapa**.  
**Branch exclusiva:** `deploy/pr6-hml-asgi` baseada em PR6A.2, que incorpora PR6A.1.  
**Produção:** `main`, `dev`, `Procfile` de produção, Vercel público e banco de produção **não são alterados**.

## 1. Confirmar capacidade e autorização

No projeto Fabroku da equipe, confirmar **antes de criar**:
- permissão/cota para **nova aplicação** de testes `backend-pires-hml`;
- plugin Dokku `redis` instalado, serviço privado vinculado ao app e versão Redis **6.2+** (GETDEL);
- serviço PostgreSQL de testes independente (sem conexão, dump ou usuários reais de produção);
- domínio HTTPS válido e proxy Nginx que faça `Upgrade` para WS e respeite idle timeout >= 300 s;
- capacidade de subir um processo ASGI com Uvicorn e pelo menos duas conexões/instâncias para verificação cross-worker;
- como o Fabroku seleciona branch de origem e processa deploys de branches que não são `main`; **não apontar a app atual para esta branch**.

O [Fabroku Backend](https://github.com/fabricadesoftware-ifc/Fabroku_BackEnd) documenta criação e vínculo de serviços Redis e PostgreSQL via Dokku e template Nginx com `proxy_set_header Upgrade`, mas a configuração da instância do IFC **ainda não foi inspecionada**.

## 2. Provisionar infraestrutura isolada

Na interface Fabroku autorizada, criar **segundo app**, com nome distinto e branch `deploy/pr6-hml-asgi` do repositório `Panificadora-Pires/backend-pires`. Nunca substitua o app `backend-pires` existente.

Criar/vincular **PostgreSQL HML** e **Redis HML** a esse app. O conector de Redis do Fabroku geralmente injeta `REDIS_URL`; o backend aceita `REALTIME_REDIS_URL` com prioridade, senão `REDIS_URL`. Só usar URLs internas; **não expor Redis na internet** nem copiar URLs/segredos para issues, chats, logs, repositórios ou capturas.

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
# DATABASE_URL e REDIS_URL entram pelo vínculo de serviços HML.
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
- verificar logs de build, PDM e migrações **apenas do banco HML**;
- verificar `GET https://<HOST_BACKEND_HML>/api/health/` e endpoints HTTP normais;
- validar login de contas de teste sem e-mails reais;
- confirmar que `POST /api/realtime/ticket/` responde **503** com `REALTIME_ENABLED=False`.

Se migrações ou acesso HTTP falharem, **parar** antes de ativar WS. Não tentar corrigir apontando `DATABASE_URL` para produção.

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
4. Manter Postgres/Redis HML isolados para diagnóstico; não reutilizar produção e não fazer merges automáticos.

## 7. Gate da produção

O PR7 só poderá propor `dev` → `main` após validação real documentada, rollback reproduzido, CI e segurança aprovados, e autorização para migração ASGI do serviço de produção. **Nunca alterar o app `backend-pires` de produção como forma de validar este roteiro**.
