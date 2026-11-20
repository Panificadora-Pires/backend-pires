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

## Gate intermediário — diagnosticar Redis no Fabroku

**Situação atual:** o app HML está Running com `GET /api/health/` retornando `{"status":"ok"}`. O serviço Redis HML foi recriado depois de exposição acidental de credencial e vinculado novamente; `REDIS_URL` deve permanecer gerenciada exclusivamente pelo Fabroku.

Antes de ativar WebSockets, mantenha `REALTIME_ENABLED=False`. Na aplicação **backend-pires-hml**, execute um **Redeploy manual somente da branch HML** após este commit, porque o webhook automático GitHub não estava disponível na primeira implantação. Após retornar a Running, use o campo de comando situado abaixo dos logs para executar exatamente:

```text
python manage.py diagnosticar_redis_hml
```

Esse comando Django existe **somente na branch `deploy/pr6-hml-asgi`**, porque o console Fabroku bloqueia corretamente `manage.py shell -c` e interpretadores arbitrários.

Resultado esperado:

```text
Redis PING: OK
Versão Redis: 7.x.x
GETDEL atômico: OK
Redis HML: PRONTO para o próximo gate
```

A versão numérica acima é **exemplo, não descoberta**. Redis precisa oferecer GETDEL (Redis >= 6.2); o teste executa SET NX com TTL de 30 segundos e GETDEL duas vezes numa chave aleatória exclusiva, sem alterar tickets nem dados do app. Se INFO estiver bloqueado, a linha de versão será `não disponível (INFO restrito)`, mas o teste GETDEL ainda comprova o requisito. O diagnóstico não imprime URL, host, senha nem conteúdo de dados reais.

Se falhar, não ative `REALTIME_ENABLED`. Verifique o vínculo REDIS_URL e a conectividade interna da HML, sem alterar o banco Neon ou o PostgreSQL da produção. Se passar, siga para o próximo gate com Origin explícito, e depois handshake WSS/ticket HTTP autenticado.

## Gate de contas fictícias HML — login sem e-mail real

O PostgreSQL Neon `pires_hml` não contém contas da aplicação principal. A HML usa
`EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend`, que não envia e-mails.
O cadastro público cria contas com `is_active=False` e exige código de verificação,
portanto **não use** `seed_dados --permitir-producao` (senha conhecida).

A branch exclusiva HML disponibiliza o comando Django `preparar_contas_hml`, que:
- recusa executar fora do domínio `backend-pires-hml.class.fabricadesoftware.ifc.edu.br` e de banco hospedado em `.neon.tech`;
- exige `HML_CONTAS_AUTORIZADAS=SIM` e três senhas **diferentes** de pelo menos 20 caracteres, validadas pelo Django;
- em uma transação cria três e-mails fictícios do domínio reservado `.invalid`, com `is_active=True` e `email_verified=True`, sem enviar e-mails:
  - admin `admin.hml@pires.invalid` (staff/superuser);
  - cliente A `cliente-a.hml@pires.invalid`;
  - cliente B `cliente-b.hml@pires.invalid`;
- nunca imprime senhas nem as grava no Git; recusa reexecução se as contas já existirem.

1. No PowerShell local, execute:

```powershell
1..3 | ForEach-Object { python -c "import secrets; print(secrets.token_urlsafe(32))" }
```

Guarde os três resultados privadamente na sequência (admin, cliente A, cliente B). Não compartilhe em chats, prints, arquivos versionados nem terminal do Fabroku.
2. No painel **somente** da aplicação `backend-pires-hml`, adicione:

```dotenv
HML_CONTAS_AUTORIZADAS=SIM
HML_ADMIN_PASSWORD=<SENHA_1_PRIVADA>
HML_CLIENTE_A_PASSWORD=<SENHA_2_PRIVADA>
HML_CLIENTE_B_PASSWORD=<SENHA_3_PRIVADA>
```

3. Faça **Redeploy** da **HML apenas**, após o commit do comando. Confirme `Running` e `GET /api/health/` OK.
4. No console de comandos do Fabroku, execute exatamente:

```text
python manage.py preparar_contas_hml
```

5. Confirme `SUCCESS`. A saída contém somente **e-mails fictícios**, não senhas. Entre via frontend `http://localhost:5173` apontado à HML, com cada e-mail e sua respectiva senha privada.
6. Assim que comprovar os logins, **exclua do painel da HML** as quatro variáveis temporárias `HML_*`, mantendo `DATABASE_URL`, `REDIS_URL` e `REALTIME_ENABLED=True`. A exclusão das variáveis não remove as contas existentes no Neon.

**Não adicionar essas contas nem variáveis à aplicação principal, ao `.env` da Vercel em produção ou às branches `dev`/`main`.**

## Gate 503 — ticket realtime não emitido (20/11/2026)

**Evidências:** autenticação e REST HML `200`, HTTPS e Uvicorn OK, Redis 8.8.0 passou `PING` e `GETDEL` (duas execuções), mas `POST /api/realtime/ticket/` mantém `503` mesmo após o restart do container. O `diagnosticar_redis_hml` não exercita `REALTIME_ENABLED` nem `emitir_ticket()`, portanto não comprova a rota de ticket. O motivo real permanece em aberto.

**Instrumentação HML-only:** a view passa a registrar somente uma linha por falha:
- `ticket_hml reason=realtime_disabled`: flag `REALTIME_ENABLED` está `False` no **processo HTTP**;
- `ticket_hml reason=emission_failed cause_type=ConnectionError` (ou outra classe): Redis/ticket falhou dentro da emissão; **sem** URI, usuário, ticket ou texto da exceção;
- `ticket_hml reason=emission_failed cause_type=none`: falha lógica sem exceção encadeada, por exemplo SET NX não reservou chave.

Além disso, o comando `python manage.py diagnosticar_ticket_hml` (restrito ao host HML e banco Neon) valida `REALTIME_ENABLED`, emite um ticket para ID fictício não existente `0` e o consome duas vezes via GETDEL. **Nenhum segredo é impresso ou persistido em logs**, e o ticket usado dura no máximo seu TTL habitual. Esse comando prova o caminho de criação/consumo no processo Django do console, mas não substitui verificar a **flag do web process** via logs da view.

### Execução segura

1. Fechar a aba do frontend local durante o diagnóstico para evitar novas tentativas automáticas de ticket.
2. Aguardar CI [HML](https://github.com/Panificadora-Pires/backend-pires/actions) aprovar os testes. Fazer **Redeploy somente de `backend-pires-hml`** para carregar as alterações de instrumentação da branch `deploy/pr6-hml-asgi`; reiniciar não baixa o novo código.
3. Confirmar HML `Running`, `GET /api/health/` OK, sem alteração de `DATABASE_URL`, `REDIS_URL` ou do banco da aplicação principal.
4. Executar no console Fabroku exatamente `python manage.py diagnosticar_ticket_hml`, inspecionar o output na API de logs (não inferir sucesso pelo badge genérico CMD do Fabroku).
5. Reabrir `http://localhost:5173/admin` (a sessão HML) e consultar os novos logs APP da HML buscando `ticket_hml reason=`. Se a rota passar a `200`, verificar handshake `wss://.../ws/v1/events/` `101` e não confundir com HMR Vite.
6. Não compartilhar headers JWT, corpo dos tickets, `REDIS_URL`, nem connection string Neon. Só depois de `200` + `101` passar aos testes de grupos/chat/pedidos.

**Este patch é temporário e não deve entrar em produção sem revisão/remoção da instrumentação.**

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
