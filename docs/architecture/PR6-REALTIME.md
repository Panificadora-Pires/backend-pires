# PR6 — Arquitetura para atualizações em tempo real

**Estado:** proposta técnica de implementação, sem habilitar WebSocket em produção.  
**Destino:** branches de recurso → `dev`; `main` somente após PR7.  
**Rastreamento:** [backend #56](https://github.com/Panificadora-Pires/backend-pires/issues/56), [frontend #73](https://github.com/Panificadora-Pires/frontend-pires/issues/73), [escalabilidade #56](https://github.com/Panificadora-Pires/frontend-pires/issues/56).

## 1. Contexto confirmado em 19/11/2026

- O Django 5.2 atende HTTP via `gunicorn app.wsgi:application` no `Procfile`. `app/asgi.py` existe, mas apenas monta o handler HTTP do Django.
- `pyproject.toml` tem Uvicorn e Python 3.12. **Não** possui `channels` ou `channels_redis`; CI usa PDM lock e testa com SQLite. `requirements.txt` é exportado do PDM.
- O front Vue 3 envia **SimpleJWT Bearer** via Axios; não usa cookies autenticados para o HTTP. A implementação de WebSocket precisa de autenticação específica, sem reaproveitar JWT de longa duração em URL.
- `AdminPedidosKanbanView.vue` consulta páginas por etapa com filtros e polling de 15 s. `adminQueueSummary.js` consulta contadores agregados a cada 15 s; chat e notificações têm seus próprios mecanismos de polling.
- `pedidos/signals.py`, `chat/signals.py` e `notificacoes/receivers.py` centralizam parte das transições. O Channels deve ser consumidor **de eventos de negócio já confirmados**, não uma nova fonte de verdade.
- Fabroku usa Dokku e documenta provisionamento opcional de Redis; **não há confirmação de um Redis vinculado ao app Pires, de suporte a Upgrade WSS/idle timeout nem de topologia de produção**. Validar antes de alterar a inicialização.

## 2. Decisões arquiteturais propostas

### 2.1 Transporte, persistência e topologia

```text
Vue (admin/aluno)
   ├── HTTP REST com JWT Bearer ───────────────┐
   │   ├── GET de dados (paginação, agregados) │
   │   └── POST de ticket WS efêmero           │
   └── wss://.../ws/... (apenas sinais) ─┐     │
                                        ▼     ▼
                                 ASGI (Uvicorn/Daphne)
                                        │
                              ProtocolTypeRouter
                                ├── HTTP → Django/DRF
                                └── WS → Channels Consumer
                                             │
                                  Redis channel layer (produção)
                                             ▲
                                       transaction.on_commit
                                  Serviços de Pedido/Chat/Notif.
```

- REST permanece fonte de verdade, incluindo preço, pagamento, QR Code, dados pessoais e autorização de comandos.
- WebSocket envia **invalidação leve** (`tipo`, `pedido_id` permitido, `versao`/timestamp e `event_id`), nunca senhas, emails, dados financeiros, código QR ou chat integral.
- Redis **centralizado** para comunicação entre workers; `InMemoryChannelLayer` somente para testes unitários, não em produção ou homologação multi-worker.
- Não criar serviço Redis automaticamente nem alterar o `Procfile` de produção neste PR documental. Confirmar compatibilidade na homologação e planejar rollback.

### 2.2 Autenticação e autorização

1. `POST /api/realtime/ticket/` autenticado por DRF SimpleJWT, com rate limit, devolve credencial **efêmera e de uso único**, associada à sessão/usuário. TTL sugerido de 30–60 segundos, sujeito a teste de relógio/rede.
2. Na conexão WS, consumir ticket **atomicamente** no backend compartilhado (Redis), validar origem `Origin`, domínio e conta ativa. Não carregar JWT access/refresh em parâmetros de URL, localStorage adicional ou logs WS.
3. Definir transporte do ticket (subprotocol ou handshake específico) durante implementação e threat model; não supor que o browser enviará `Authorization` no handshake.
4. Cliente comum: apenas grupos de seu usuário e pedidos que possui; administrador: sinalização operacional global permitida, sem expor payload de outros clientes.
5. Checar autorização novamente ao ingressar em sala de pedido; considerar revogação/expiração e fechar conexões em troca de sessão ou desativação.
6. WS começa **somente leitura para eventos**: nenhuma alteração de status, chat, pagamento ou retirada via socket nesta fase. Essas ações permanecem nos endpoints HTTP auditados.
7. `OriginValidator` / `AllowedHostsOriginValidator`, `wss://` obrigatório em ambientes públicos e TLS no Redis conforme provedor.

### 2.3 Contrato de eventos, versão 1

Exemplos ilustrativos; a especificação final fica no contrato API+frontend e nos testes:

```json
{"v":1,"tipo":"pedido.atualizado","pedido_id":123,"event_id":"...","emitido_em":"..."}
{"v":1,"tipo":"pedido.criado","pedido_id":124,"event_id":"...","emitido_em":"..."}
{"v":1,"tipo":"chat.mensagem_nova","pedido_id":123,"event_id":"...","emitido_em":"..."}
{"v":1,"tipo":"notificacao.alterada","event_id":"...","emitido_em":"..."}
```

- A UI valida `v/tipo`, deduplica `event_id`, descarta sinais de sessão anterior e **reconsulta** REST com filtros e páginas preservados.
- Emitir somente com `transaction.on_commit`, após operações de negócio confirmadas; proibir notificação de transação revertida.
- Recarregar apenas recursos/colunas afetados e resumos globais, respeitando debounce para rajadas e `inFlight`; não baixar catálogo/pedidos inteiros.
- Não depender de recebimento garantido de sinais; na reconexão, resincronizar via REST para evitar perdas.

### 2.4 Fallback e segurança operacional

- **Antes da conexão estável:** polling atual continua funcionando.
- **WS conectado e saudável:** desativar polling redundante somente nas telas já migradas; outros fluxos continuam como estão.
- **WS indisponível/Redis offline/proxy falha:** retomar polling nos intervalos atuais (ex.: Kanban/contadores 15 s), manter dados antigos visíveis com aviso de falha honesto.
- Reconexão com backoff exponencial + jitter, limite de tentativas, pausa offline/background e nova autenticação; evitar `setInterval` acumulado após montagem/desmontagem.
- Monitorar conexões abertas, rejeições 401/403, tempo de reconexão, lag dos eventos e falha na camada Redis; não registrar tickets/tokens.

## 3. Fases de entrega

**PR6A.1 — infraestrutura de homologação**

- Confirmar Redis privado e WebSocket Upgrade no Fabroku/Dokku, limites de timeout e TLS. Se indisponível, parar habilitação e manter REST/polling.
- Adicionar `channels` e `channels_redis` em `pyproject.toml`, atualizar `pdm.lock` e `requirements.txt` via PDM.
- Montar ASGI com HTTP preservado e WS restrito; desenvolver tickets one-time, middleware e testes com `WebsocketCommunicator`.
- Validar ASGI sob Uvicorn/Daphne em homologação com dois processos e Redis compartilhado. Alterar `Procfile` somente em PR isolado para staging, com comando de rollback documentado.

**PR6A.2 — produtores de eventos**

- Instrumentar criação/status de pedidos, chat e notificações com `on_commit`; isolamento de grupos e testes de permissões.
- Eventos minificados/versionados, envio não-bloqueante que não altera resultado de transação HTTP; observabilidade e retry de leitura via REST.

**PR6B — frontend Vue 3**

- Serviço central de conexão e ticket, separação de sessão, retry/backoff, heartbeat, validação e deduplicação de eventos.
- Reconsultar Kanban, contadores, chat, notificações e pedidos do aluno usando stores existentes; reduzir polling somente quando há estabilidade.
- Testes de duas abas, admin/cliente, reconexão, erro offline, múltiplos usuários, 3.001+ registros e mobile.

**PR7 — homologação e release**

- Testes PostgreSQL + Redis + WSS real no Fabroku (duas conexões/instâncias), pagamento Mercado Pago, QR Code, chat, logout/troca de conta, acessibilidade/390px.
- Deploy controlado com rollback para `gunicorn app.wsgi:application` e polling se infraestrutura falhar.
- Auditoria com Codex, verificação de métricas e só então considerar `dev` → `main`.

## 4. Critérios de aceite antes de liberar WebSocket

- [ ] O usuário anônimo não obtém ticket, e cliente não consegue se inscrever na fila global.
- [ ] Cliente não lê eventos de pedido de outro cliente; admin autorizado vê somente os sinais necessários.
- [ ] Ticket consumido apenas uma vez e expira; origem e protocolo validados.
- [ ] Nenhum evento é publicado antes de commit, nem para transação revertida.
- [ ] Staging prova entrega cross-worker via Redis e reconexão após reinício.
- [ ] HTTP/pagamentos/QR funcionam sem regressão; fallback opera sem Redis.
- [ ] O serviço roda em ASGI em homologação; produção permanece WSGI até aprovação explícita da release.
- [ ] CIs, acessibilidade, QA real e runbook operacional aprovados.

## 5. Referências técnicas

- [Django Channels — Deployment](https://channels.readthedocs.io/en/stable/deploying.html)
- [Django Channels — Channel layers](https://channels.readthedocs.io/en/stable/topics/channel_layers.html)
- [Channels Redis — configuração e segurança](https://github.com/django/channels_redis)
- [Fabroku_BackEnd — documentação de Redis opcional e Dokku](https://github.com/fabricadesoftware-ifc/Fabroku_BackEnd)
