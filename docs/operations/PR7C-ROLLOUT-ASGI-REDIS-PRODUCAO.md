# PR7C — Ativação controlada de ASGI/Redis na produção da Pires

**Situação:** planejamento de release, **não** autorização para alterar ambiente Fabroku, banco real ou `main`.

## O que já está pronto

- Backend `dev` já possui Django Channels, emissão de ticket efêmero por HTTP, autenticação WSS, `channels_redis`, `OriginValidator`, eventos de pedido/chat/notificações e fallback REST no frontend.
- Em `dev`, `app/asgi.py` já executa HTTP com `REALTIME_ENABLED=False`; configura websocket somente ao habilitar a flag.
- `dev/Procfile` ainda executa **`gunicorn app.wsgi:application`**, portanto não cria listener WS.
- A HML `backend-pires-hml` usa `uvicorn app.asgi:application --host 0.0.0.0 --port 5000 --ws wsproto`, banco Neon **separado** e Redis HML; WebSocket 101, tickets, chat/notificações, isolamento A/B e fallback pedidos/polling foram aprovados manualmente.
- Não mesclar [backend PR #61](https://github.com/Panificadora-Pires/backend-pires/pull/61): contém comandos e configurações somente de HML (incluindo reset de senhas).
- A revisão de [PR7 — #62](https://github.com/Panificadora-Pires/backend-pires/issues/62) ainda contém gates de pagamentos, auditoria, testes >3000 registros, multiworker e rollback.

## Bloqueios atuais para Redis/WSS em produção

- [ ] Testar **dois processos ASGI reais**, com Redis compartilhado na HML, demonstrando entrega de eventos entre workers, isolamento, concorrência, reinício e reconexão/fallback.
- [ ] Provisionar **Redis privado e separado** para produção, com controle de acesso, backup/recuperação apropriados, limites e recursos. Há histórico de cota Fabroku 2/2 para serviços (PostgreSQL produção + Redis HML); confirmar a cota antes de provisionar. **Nunca reutilizar** `backend-pires-hml-redis`, contas fictícias ou banco Neon de HML.
- [ ] Revisar configuração de rede, portas e proxy HTTPS/WSS na aplicação de produção, inclusive `Origin`, endpoint `/api/realtime/ticket/`, status 101 e expiração dos tickets.
- [ ] Revisar segurança: não vazar URL de Redis, tokens, JWT, dados privados, tickets, dados de cartão/QR em logs, status públicos ou PRs.
- [ ] Homologar regressões de pagamento Mercado Pago sandbox, idempotência, falhas de rede/Redis e autorização multiusuário. Este documento não marca esses testes como aprovados.
- [ ] Garantir métricas mínimas (HTTP/WS, erros 5xx, uso memória, conexões Redis, reconexões) e janela com rollback preparado.

## Rollout proposto (duas ativações distintas)

### Fase A — Migrar transporte para ASGI sem realtime
1. Abrir **PR de código separado** baseado na `dev` que altera apenas o comando `web` de produção para ASGI/uvicorn, após comparar as configurações, porta `PORT`, proxy e recursos do Fabroku. Não copiar o Procfile HML cegamente.
2. Com CIs verdes e aprovação, numa janela controlada fazer backup/verificar migrations e publicar o backend **com `REALTIME_ENABLED=False`**. Frontend mantém `VITE_REALTIME_ENABLED=false` (variável de build; mudar exige novo deploy). Assim a API continua HTTP sem ativar WS.
3. Smoke tests no backend de produção: `/api/health/`, login/refresh/logout, catálogo, pedidos, admin, chat, notificações, endpoints do checkout e QR; monitorar 4xx/5xx/latência/memória. **Nenhuma mudança automática em pagamento ou dados.**
4. Em caso de falha, reverter o deploy para a revisão anterior Gunicorn WSGI, manter flags false e confirmar saúde/fluxos de pedidos. Não apagar nem restaurar banco sem análise das migrations.

### Fase B — Ativar Redis e WSS (aprovação separada)
1. Somente após os bloqueios e fase A aprovados: ligar `REDIS_URL` privado de produção e `REALTIME_ALLOWED_ORIGINS` explícitas (somente origens reais da aplicação), e então `REALTIME_ENABLED=True` no backend, com restart/deploy controlado.
2. Comprovar `POST /api/realtime/ticket/` 200, `wss://<dominio-real>/ws/v1/events/` 101 + `pires.v1`, entrega entre workers para pedidos/chat/notificações, isolamento usuário A/B, fallback com Redis/WS indisponível e nenhum erro financeiro.
3. Apenas depois, configurar no **build** do frontend de produção `VITE_REALTIME_ENABLED=true` e publicar o frontend numa etapa separada. Revalidar pedidos, chat/notificações, desconexões, login e uso real.
4. Rollback imediato de WSS: desfazer `VITE_REALTIME_ENABLED` no build e `REALTIME_ENABLED` backend, mantendo REST/polling; se ASGI também apresentar problema, reverter para o processo WSGI da fase anterior. Preservar pedidos e banco.

## HML — limpeza imediata de segredos temporários

Após concluir o reset das contas fictícias, **remover do painel privado somente**:
- `HML_REDEFINICAO_AUTORIZADA`
- `HML_NOVA_SENHA_ADMIN`
- `HML_NOVA_SENHA_CLIENTE_A`
- `HML_NOVA_SENHA_CLIENTE_B`

Não apagar `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `REALTIME_ALLOWED_ORIGINS` nem alterar `REALTIME_ENABLED` inadvertidamente. Manter as novas senhas em gerenciador de senhas. Não expor valores nem usar botão `Exportar .env` em canal público.

## Estado em 24/11/2026

- **Entre workers na HML: aprovado.** Com `uvicorn --workers 2` e o Redis HML ([#70](https://github.com/Panificadora-Pires/backend-pires/pull/70)), 3 de 3 rodadas de `scripts/hml_pr7c_cross_worker.py` foram aprovadas. Cada rodada teve 12 WebSockets e 24 respostas HTTP atendidas por 2 PIDs. Todas as conexões do cliente A e do admin receberam os mesmos 7 eventos, e o cliente B recebeu 0. Pendente: reconexão medida após reinício do Redis ou do backend.
- **Fase A pronta para revisão:** o `Procfile` usa `sh -c 'exec uvicorn app.asgi:application --host 0.0.0.0 --port "${PORT:-5000}" --ws wsproto --workers 2'`. É a mesma linha da HML, mas lê a porta de `PORT`. Com `REALTIME_ENABLED=False`, `app.asgi.application` é o `ASGIHandler` do Django puro, sem Redis (teste `realtime/test_asgi_sem_realtime.py`). Comando validado localmente com `PORT=8765`: dois workers e health 200. O `requirements.txt` usado pelo `build.sh` já contém `uvicorn`, `wsproto` e `channels`, e o `pip-audit` não encontrou vulnerabilidades.
- **Release `main...dev` no backend:** nenhuma migration nova; as variáveis novas são só `REALTIME_*` e `THROTTLE_REALTIME_TICKET`, todas com padrão seguro (realtime desligado).
- **Decisão sobre o Redis (responsável, 24/11/2026):** a cota do Fabroku está em 2/2. Quando os testes de realtime na HML terminarem, o `backend-pires-hml-redis` será apagado e um Redis exclusivo será criado para a produção, apenas na Fase B. A Fase A não usa Redis. Ao remover o Redis da HML, colocar `REALTIME_ENABLED=False` na HML, cujos testes de WebSocket deixam de ser possíveis.
- **Rollback da Fase A:** voltar o `Procfile` para `gunicorn app.wsgi:application --log-file -` e fazer redeploy. Nenhuma migration está envolvida.

### Comportamento do Fabroku observado na HML (24/11/2026)

- **Editar** uma variável existente no painel **não** chega ao container nem com "Reiniciar". Só passou a valer depois de um **Redeploy**: `REALTIME_ENABLED=False` só desligou o ticket (503) após o redeploy. **Adicionar** variáveis reinicia a app. Na Fase B, ligar o `REALTIME_ENABLED` exige redeploy, e o rollback de emergência também.
- "Reiniciar" e "Redeploy" são **sem tempo fora do ar**: `/api/health/` ficou 200 durante todo o processo. As conexões WebSocket abertas fecham com `1012`, e o frontend reconecta em cerca de 2 s.
- **Reconexão aprovada:** depois do reinício, o frontend abriu um ticket e um WebSocket novos sozinho. Um evento do admin chegou em 2 s pela conexão nova. A expiração `4401` (300 s) reconecta em 2 s.
- **Fallback aprovado:** com o realtime desligado, o ticket responde 503, o frontend não reabre o WebSocket e "Meus pedidos" continua atualizando por polling (cerca de 10 s), mostrando o pedido pronto sem recarregar.
- **Com `REALTIME_ENABLED=True` e sem Redis, a app não sobe** (`settings.py` exige `REALTIME_REDIS_URL` válido). Por isso a ordem é: primeiro `REALTIME_ENABLED=False` + redeploy, depois remover o Redis.
- O painel não tem ação para reiniciar o Redis nem para fazer backup do Postgres. O backup é feito pela CLI (`fabroku run dumpdata --django --output ...`).

### Estado da HML após o PR7C

`REALTIME_ENABLED=False`, `backend-pires-hml-redis` **removido** (24/11/2026) para liberar a cota. A HML segue útil para HTTP, pagamentos em sandbox e escala, mas não para WebSocket. Para voltar a testar realtime na HML, é preciso um Redis de novo.

## Evidências e aprovação

- [ ] Aprovação dos gates [#62](https://github.com/Panificadora-Pires/backend-pires/issues/62) e do QA escalabilidade [frontend #56](https://github.com/Panificadora-Pires/frontend-pires/issues/56).
- [ ] PR ASGI produção específico e revisado, CI e teste de porta/proxy Fabroku.
- [ ] Checklist de janela de release, responsáveis e rollback.
- [ ] Autorização expressa de merge `dev` → `main` e **deploy de produção**.
- [ ] Autorização separada para habilitar Redis/WSS depois de ASGI estável.

> `GET /` retornar 404 numa API Django sem rota raiz não demonstra que o serviço está fora do ar. Validar pelo `/api/health/`; o campo "Nenhum deploy ainda" do painel pode estar desatualizado mesmo com a aplicação Running, e não substitui logs/commit reais.
