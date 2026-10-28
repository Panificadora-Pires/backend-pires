# CLAUDE.md — Backend da Pires Panificadora

Backend Django + DRF da **Pires Panificadora**. As regras gerais (git, segurança, testes, formato da resposta) estão no `CLAUDE.md` da pasta pai. Contexto mestre: `../contexto.md`. Plano da fase: `../docs/planos/`.

## Arquitetura: apps por domínio

- Apps: `core` (usuários, auth, convites, verificação), `catalogo`, `pedidos`, `favoritos`, `notificacoes`. Domínio novo ganha app próprio (ex.: `chat`, `chatbot`), registrado em `INSTALLED_APPS` e em `app/urls.py`.
- Comunicação entre apps por **signals** (veja `pedidos/signals.py` e `notificacoes/receivers.py`) ou chamadas a serviços, sem dependência circular.
- Regra de negócio e operações transacionais em `services/` do app (`pedidos/services/pedido.py`, `pagamentos.py`, `expiracao.py`). Views só orquestram.
- Models, serializers e views em pacotes, um arquivo por entidade, exportados no `__init__.py` (estilo `from .x import A, B`; o ruff ignora esses arquivos, não rode `--fix` neles).
- Fluxo de toda API: **Model → Serializer → ViewSet → Router → URL**. Rota: `router.register(...)` em `app/urls.py`.

## Model

- Classe no singular; `__str__` sempre; `verbose_name` em português.
- `ForeignKey` com `on_delete` pensado (`CASCADE`, `PROTECT` ou `SET_NULL`) e sempre `related_name`.
- Opções fixas com `models.TextChoices` dentro da model (veja `Pedido.Status`).
- Unicidade e índices em `Meta` (`UniqueConstraint`, `indexes`).
- Depois de mudar model: `pdm run python manage.py makemigrations` e conferir a migration gerada.

## Serializers

- Um por ação quando leitura e escrita diferem (`ProdutoListSerializer`, `ProdutoDetailSerializer`, `ProdutoWriteSerializer` em `catalogo` são a referência). `fields` explícito, nunca `'__all__'`.
- Campo exibido mas não gravável: `read_only=True`. Autor/usuário vem do `request.user`, nunca do corpo.
- Gravação em mais de uma tabela com `@transaction.atomic`.
- Validação com `validate_<campo>` e `validate`, mensagens em português.

## ViewSet e permissões

- **Permissão padrão: `IsAuthenticated`.** Rota pública declara `AllowAny` de propósito (login, registro, verificação, reset, Google, webhook do Mercado Pago, `health`).
- Pedidos e recursos do cliente: `IsAuthenticated` + `IsOwnerOrAdmin` (`core/permissions.py`). `get_queryset` **sempre** restringe ao que o usuário pode ver (cliente só vê os próprios; `is_staff` vê tudo).
- Ações extras com `@action` + `@extend_schema(summary=...)`. Filtros com `DjangoFilterBackend` e `filterset_fields`.
- Throttle por escopo para rotas sensíveis (`throttle_scope`), com as taxas em `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`.
- Paginação: `app/pagination.py` (`page_size` até 100; a resposta traz `count`, `next`, `previous`, `page`, `page_size`, `total_pages`, `results`).

## Regras que não podem quebrar

Veja `../contexto.md` (seção 6): fluxo de status, preço e estoque no servidor, reserva e devolução de estoque uma única vez, checkout idempotente, Mercado Pago como fonte de verdade, QR de retirada e relatórios. Ao mexer em `pedidos/`, rode **toda** a suíte.

## Testes

- `APITestCase`/`TestCase` em `<app>/tests/test_<assunto>.py`. Para `pedidos`, reutilize `pedidos/tests/base.py` (`CriaUsuariosEProdutosMixin`).
- Para chamadas externas (Mercado Pago, Google, e-mail), use `unittest.mock.patch`, nunca rede real.
- Cubra: sem login (401), recurso de outro usuário (403/404), caminho feliz, validação (400) e limites.
- Antes de dizer que terminou:
  - `pdm run python manage.py test`
  - `pdm run python manage.py check`
  - `pdm run python manage.py makemigrations --check --dry-run`
  - `pdm run ruff check <arquivos alterados>` (não corrigir os avisos antigos fora do escopo da tarefa)

## Estilo e ambiente

- Ruff: linha de 120 colunas, aspas simples, ordenação de imports. Docstrings e mensagens em português.
- Variáveis novas entram em `.env.example` e `.env.production.example`, com comentário. Nunca versionar valores reais.
- Conflito de migrations em desenvolvimento: apagar `db.sqlite3` e regenerar (nunca em produção).
- `seed_dados` só roda com `DEBUG=True`.

## Commits

Conventional Commits em português: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`. Autor Arthur Lanznaster, sem `Co-Authored-By` e sem rodapé do Claude. Branch da fase a partir da `main`; nunca direto na `main`.
