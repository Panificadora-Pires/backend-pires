# PR6A.2 — Eventos após commit (integração com PR6A.1)

**Estado:** implementação em branch isolada. **Não ativar em produção**.  
**Base técnica:** PR6A.1 (`feat/pr6a1-channels-infra`), ainda Draft.  
**Feature flag:** `REALTIME_ENABLED=False` por padrão. Polling Vue permanece ativo.

## Eventos v1

Cada sinal tem apenas `v=1`, `tipo`, `event_id` aleatório, `emitido_em` e opcionalmente `pedido_id`. **Sem status, preços, mensagens, e-mail, QR Code ou credenciais**.

| Tipo | Quando | Destinos |
| --- | --- | --- |
| `pedido.criado` | Pedido.save(created=True), incluindo checkouts em dinheiro/online | Operadores; dono do pedido |
| `pedido.atualizado` | Status/estado de pagamento alterado por Kanban, QR, expiração ou webhook | Operadores; dono do pedido |
| `chat.mensagem_nova` | Mensagem salva no chat | Operadores; dono do pedido |
| `chat.leitura_atualizada` | Leitura em lote de mensagens | Operadores; dono do pedido |
| `notificacao.alterada` | Nova notificação ou alteração de leitura, inclusive `update()` em lote | Somente dono da notificação |

Os grupos válidos são `pires-admin-eventos` e `pires-usuario-<id>`. O consumer do PR6A.1 **não aceita que o cliente escolha outro grupo**: o grupo vem da identidade validada no handshake. Os eventos são apenas gatilhos para **reconsultar os recursos REST autorizados**.

## Commit, falhas e idempotência

- `realtime.signals`, registrado em `RealtimeConfig.ready()`, observa `post_save` de Pedido, Mensagem e Notificacao. Com `REALTIME_ENABLED=False`, nenhuma publicação é agendada e mensagem não executa consulta extra de conversa.
- `QuerySet.update()` e `bulk_create()` **não disparam** `post_save`. Foram instrumentadas explicitamente as alterações em lote conhecidas de leitura em `chat/services/chat.py`, `notificacoes/receivers.py` e `notificacoes/views.py`.
- Usa `transaction.on_commit` para não enviar eventos de transações abortadas. Vários saves relevantes em uma transação podem produzir vários sinais; o cliente deve agrupar, deduplicar por `event_id`, e fazer refresh somente dos recursos necessários.
- O transporte por Redis é **best effort**: timeout de até 1 segundo por publicação e erros limitados a log sem dados sensíveis. Falhas **não** devem reverter checkout, pagamento, retirada por QR ou envio de chat. Como não há outbox persistente nem garantia de entrega, o polling e a ressincronização ao reconectar são obrigatórios.
- Sinais não incluem dados que permitam reproduzir QR ou informações de pagamento.
- Atualizações que usem `QuerySet.update` fora dos pontos instrumentados podem precisar de publicação explícita em futuras mudanças do domínio.

## Verificação

```powershell
pdm sync
pdm run python manage.py check
pdm run python manage.py makemigrations --check --dry-run
pdm run python manage.py test realtime --noinput --verbosity 2
pdm run python manage.py test --noinput --verbosity 1
```

**Gates antes de disponibilizar ao frontend:** Redis real com dois processos, WSS Fabroku, retry/reconexão, revogação/logout, isolamento entre duas contas, queda do Redis, monitoramento de tempo de entrega, regressão de pagamentos e QR. A implementação continua **fora de `dev` e `main`** até esses critérios.

## Driver WebSocket e homologação

O PR6A.1 agora inclui `wsproto` no lock PDM e pode aceitar `REDIS_URL` privado fornecido pelo Fabroku. Essas correções foram incorporadas à branch PR6A.2 por merge de feature (PR #60). Para validar o transporte real, usar o [runbook HML](https://github.com/Panificadora-Pires/backend-pires/blob/deploy/pr6-hml-asgi/docs/operations/FABROKU-PR6-HOMOLOGACAO.md) e a branch `deploy/pr6-hml-asgi`, **sem alterar o app de produção**. O CI unitário não substitui o handshake WSS/Redis de homologação.
