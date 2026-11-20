# PR7A — Auditoria inicial de baseline e segurança (20/11/2026)

**Escopo:** revisão estática dos repositórios `Panificadora-Pires/backend-pires` e `frontend-pires`, branches `dev` e `main`; consulta a CI e evidências existentes. **Não é pentest, varredura de dependências nem auditoria do ambiente Fabroku**, e não autoriza publicação.

**Decisão provisória:** **NÃO LIBERAR** o merge global `dev → main` ou a ativação de ASGI/Redis/WSS na produção até cumprir os gates abaixo. O `backend-pires-hml` continua isolado e útil para testes. Não foram lidos valores de secrets, logs privados do Fabroku nem dados dos usuários reais.

## 1. Linha de base observada

| Item | Evidência de código / CI | Situação |
| --- | --- | --- |
| Backend `dev` vs `main` | [Comparação oficial](https://github.com/Panificadora-Pires/backend-pires/compare/main...dev) | Históricos divergem: `dev` 97 commits à frente da base comum, 1 atrás, 45 arquivos reportados pela comparação; **não equivale a 97 mudanças de produção** |
| Frontend `dev` vs `main` | [Comparação oficial](https://github.com/Panificadora-Pires/frontend-pires/compare/main...dev) | Históricos divergem: `dev` 172 à frente e 1 atrás, 233 arquivos reportados; revisar diff e migrations/contratos para release |
| Backend `dev` | [CI backend PR #64](https://github.com/Panificadora-Pires/backend-pires/actions/runs/44829839756) | **270 testes Django**, `manage.py check` e verificação de migrations sem alterações: sucesso em SQLite de teste. Não executou `check --deploy` no ambiente real |
| Frontend UX2/UX3 | [CI frontend PR #84](https://github.com/Panificadora-Pires/frontend-pires/actions/runs/44828535490) | **236 testes**, build Vite/PWA: sucesso. Não comprova integração Mercado Pago nem rede/proxy |
| Backend `dev` | [Procfile](https://github.com/Panificadora-Pires/backend-pires/blob/dev/Procfile) | `gunicorn app.wsgi:application`; HTTP/polling em produção. ASGI, Channels, ticket e `channels_redis` já implementados em `dev`, mas não habilitados na produção |
| Frontend `dev` | [Exemplo de ambiente](https://github.com/Panificadora-Pires/frontend-pires/blob/dev/.env.example) | `VITE_REALTIME_ENABLED=false` por padrão. A flag é compilada no build; não basta trocar env após publicar |
| HML | [PR HML #61](https://github.com/Panificadora-Pires/backend-pires/pull/61) | WSS 101, ticket, pedidos, chat/notificações, isolamento A/B e fallback documentados como aprovados manualmente. **Não portar o PR #61:** contém Procfile e comandos exclusivos de homologação |

**Importante:** os valores/serviços efetivamente configurados na aplicação de produção (DEBUG, Redis, SSL, Mercado Pago, SMTP, banco, Vercel) **não foram verificados** nesta auditoria de código. As quatro variáveis `HML_NOVA_SENHA_*` e `HML_REDEFINICAO_AUTORIZADA` foram **informadas pelo responsável como removidas**, sem inspeção independente do painel.

## 2. Achados e riscos — com severidade

| ID | Prioridade | Estado | Evidência e consequência possível | Gate / ação requerida |
| --- | --- | --- | --- | --- |
| R-01 | **Bloqueante de release** | Confirmado | `main` e `dev` divergentes em ambos os repos. Integrar sem revisão de diff/contratos pode carregar regressões do painel/admin, checkout, auth, migrations e realtime | Auditar comparação integral, separar alterações não relacionadas, revisar migrations, testar integração em HML e montar PRs de release individuais |
| R-02 | **Bloqueante de realtime** | Confirmado | `dev/Procfile` é WSGI, enquanto [`app/asgi.py`](https://github.com/Panificadora-Pires/backend-pires/blob/dev/app/asgi.py) serve WS apenas com flag. Redis HML não deve virar Redis de produção. Multiworker real não comprovado | Seguir [PR7C #64](https://github.com/Panificadora-Pires/backend-pires/pull/64): ASGI primeiro com flag false; depois Redis prod próprio + teste cross-worker, WSS, rollback e autorização separada |
| R-03 | **Alta — robustez de configuração** | Confirmado no código, efeito real não verificado | [`settings.py`](https://github.com/Panificadora-Pires/backend-pires/blob/dev/app/settings.py#L38-L57): `DEBUG` usa fallback `True`; [DB](https://github.com/Panificadora-Pires/backend-pires/blob/dev/app/settings.py#L358-L364) cai para SQLite se `DATABASE_URL` faltar. Com variáveis ausentes em um deploy, pode inicializar em modo de desenvolvimento ou contra banco indevido | Em PR isolado, adicionar **fail-closed explícito para ambiente de produção** + testes de startup sem `DEBUG=False`/`DATABASE_URL`; verificar variáveis de produção sem publicar seus valores |
| R-04 | **Alta — HTTPS/proxy** | A confirmar no ambiente | [`settings.py`](https://github.com/Panificadora-Pires/backend-pires/blob/dev/app/settings.py#L107-L128): confia em `X-Forwarded-Proto`, `SECURE_SSL_REDIRECT=False` e `SECURE_HSTS_SECONDS=0` por padrão; pode estar correto com proxy TLS terminando e redirecionando, mas precisa prova | Conferir redirecionamento HTTP→HTTPS e `X-Forwarded-Proto` sanitizado pelo proxy. Executar `python manage.py check --deploy` com **configuração equivalente à real**, sem logs com segredos. Ajustar HSTS/redirect só após confirmar domínio/proxy |
| R-05 | **Alta — pagamentos** | Contratos observados; sandbox integrado pendente | [Checkout Django](https://github.com/Panificadora-Pires/backend-pires/blob/dev/pedidos/views/pedido.py#L104-L254) reutiliza `checkout_id` e [Orders API](https://github.com/Panificadora-Pires/backend-pires/blob/dev/pedidos/services/pagamentos.py#L208-L218) usa `X-Idempotency-Key`. [Webhook](https://github.com/Panificadora-Pires/backend-pires/blob/dev/pedidos/views/pedido.py#L292-L387) exige HMAC em produção, **desde que `MERCADO_PAGO_SANDBOX=False`**. Concorrência, timeout, status e reembolso precisam prova externa | Verificar `MERCADO_PAGO_SANDBOX=False` na produção (sem revelar valores), executar sandbox para aprovação/recusa/duplicação/timeout/webhook assinado/sem assinatura/estorno e QR. Revisar se campo `provider: exc.data` em erros de checkout contém dados que não devem chegar ao cliente |
| R-06 | **Alta — armazenamento de credenciais** | Confirmado no frontend; impacto depende de XSS | [`api.js`](https://github.com/Panificadora-Pires/frontend-pires/blob/dev/src/services/api.js#L23-L51) armazena access/refresh JWT em `localStorage` para persistência. Isso aumenta impacto potencial de qualquer XSS; há reconciliação de sessão, mas não proteção contra script malicioso da mesma origem | Revisar CSP, injeções/templates, dependências, vetores de XSS e política de persistência/TTL. Não migrar para cookies às pressas sem desenho de CSRF/compatibilidade |
| R-07 | **Média/alta — dependências** | Não auditado | Locks `pdm.lock` e `package-lock.json` mudaram desde `main`; CI frontend usa `npm ci --no-audit`. Testes/build verdes não equivalem a ausência de CVEs | Executar auditorias autenticadas de dependências com versão resolvida do lock, classificar severidade/explorabilidade, corrigir em PR isolado com regressão. Não executar `npm audit fix --force` |
| R-08 | **Média/alta — escala** | Pendente | [Frontend #56](https://github.com/Panificadora-Pires/frontend-pires/issues/56) relata paginação e agregados implementados, mas QA integrado com 3.001+ registros, filtros, sessão, checkout/QR e banco real não concluído | Preparar dataset sintético na HML e testar tempo de resposta/consumo, sem copiar produção |
| R-09 | **Média — autenticação e dados** | Parcialmente coberto por código | [DRF](https://github.com/Panificadora-Pires/backend-pires/blob/dev/app/settings.py#L444-L499) exige usuário logado por padrão e usa throttles; [JWT](https://github.com/Panificadora-Pires/backend-pires/blob/dev/app/settings.py#L513-L527) rotaciona refresh e permite access token de 3h. Logout/aba, troca de senha, contas inativas e endpoints privados precisam testes de abuso | Exercitar A/B/admin, logout e token anterior, conta inativa, caminhos diretos, chat/QR/permissões e redigir evidência sem dados pessoais |
| R-10 | **Média — operabilidade** | Não comprovado | Não há comprovação de backup/restauração de banco produção, capacidade Redis, alertas, rollback de migrations compatíveis nem teste cross-worker real | Definir restore ensaiado, observabilidade, limiares, janela de release e responsável; não ligar WSS até isso estar pronto |

**Controles positivos, mas não suficientes:** segredo Django obrigatório quando `DEBUG=False`, cookies `Secure` quando não debug, `IsAuthenticated` global, throttles, HMAC do webhook fora de sandbox, tickets WS de uso único (GETDEL) e execução HTTP/Polling sem Redis quando flags desligadas. Verificar configurações de produção antes de tratar qualquer controle como efetivamente habilitado no servidor.

## 3. Ações executáveis em ordem

### PR7A.1 — Gate de configuração segura (prioridade imediata)
- [ ] Abrir PR específico com testes: ao definir ambiente como produção, **recusar startup** sem configuração explícita de `DEBUG=False`, `DATABASE_URL` PostgreSQL e `SECRET_KEY` forte; sem quebrar desenvolvimento/CI SQLite.
- [ ] Executar `manage.py check --deploy` com env controlado e seguro, conferir avisos pertinentes; comparar com [checklist oficial Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- [ ] Inspecionar o proxy Fabroku (redirecionamento TLS, `Host`, `X-Forwarded-Proto`) e documentar evidência sanitizada.

### PR7A.2 — Autenticação, pagamentos e dependências
- [ ] Testar `MERCADO_PAGO_SANDBOX=False` sem acesso real em CI e comprovar configurações por verificação **booleana** no painel de produção, sem extrair secrets.
- [ ] Reproduzir idempotência com duas requisições concorrentes ao mesmo `checkout_id`, falha de rede e webhook duplicado/assinado/inválido no sandbox isolado.
- [ ] Revisar dados retornados no erro `provider: exc.data`, logs, JWT em `localStorage`, política CSP/XSS e retenção de dados.
- [ ] Auditar dependências resolvidas e documentar correções e suas regressões.

### PR7B e PR7C — Só depois
- [ ] Escala 3.001+ registros na HML, testes de ponta a ponta com PostgreSQL/sandbox.
- [ ] Dois processos ASGI distintos recebendo eventos via Redis comum **somente na HML**; teste de queda, reconexão, isolamento e fallback.
- [ ] Preparar Redis exclusivo de produção, custo/cota, plano de ASGI sem WS e rollback.
- [ ] Aprovação explícita para atualizar `main`, depois para deploy e, **separadamente**, para ativar WSS.

## 4. Sem ações sobre produção

Este relatório não executou nem autorizou: merge em `dev`/`main`, alterações de Procfile, variáveis do Fabroku, banco Neon, Redis, Mercado Pago, deploy Vercel ou migrações. Todas as evidências de funcionalidade HML referem-se aos testes anteriores e podem exigir repetição após novos commits.

**Referências técnicas:** [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [Channels — Deploying](https://channels.readthedocs.io/en/stable/deploying.html), [Channels — Channel Layers](https://channels.readthedocs.io/en/stable/topics/channel_layers.html), [PR7 roadmap #62](https://github.com/Panificadora-Pires/backend-pires/issues/62).
