# Backend — Sistema de Cantina Escolar (IFC)

Documentação técnica do backend: o que é, como rodar, e tudo que a API oferece hoje.

---

## 1. O que é

API REST em Django + Django REST Framework para o sistema de pré-pedidos da cantina do IFC. Alunos reservam produtos antes do intervalo; a administração controla estoque, promoções, categorias e o fluxo de preparo/retirada dos pedidos.

Construído em cima do template Django do professor Marco André Mendes ([`template_django_pdm`](https://github.com/marrcandre/template_django_pdm)), gerenciado com [PDM](https://pdm-project.org/).

### Stack

| Camada | Tecnologia |
|---|---|
| Linguagem / Framework | Python 3 + Django 5 |
| API | Django REST Framework |
| Autenticação | JWT (`djangorestframework-simplejwt`) |
| Banco (local) | SQLite |
| Banco (produção) | PostgreSQL, via `dj-database-url` |
| Imagens | Cloudinary (`django-cloudinary-storage`), com fallback pra disco local se `CLOUDINARY_URL` não estiver definida |
| Documentação da API | drf-spectacular (Swagger/Redoc automáticos) |
| Filtros | django-filter |
| Gerenciador de pacotes | PDM |

### Estrutura de apps

O backend é dividido em 4 apps Django, cada um com responsabilidade única:

```
core/          → Usuário (login por e-mail), autenticação JWT, permissões compartilhadas
catalogo/      → Categoria, Produto, Promoção (o "cardápio")
pedidos/       → Pedido, ItemPedido, QR Code de retirada, regras de negócio do pedido
notificacoes/  → Notificação ao aluno (escuta eventos de pedidos via Django Signal)
```

Dentro de cada app, quando há mais de um model/serializer/view, eles ficam em pastas (`models/`, `serializers/`, `views/`) com um arquivo por entidade — em vez de um `models.py` gigante.

`pedidos` depende de `catalogo` (um `ItemPedido` referencia um `Produto`). `notificacoes` depende de `pedidos` (escuta o signal `pedido_ficou_pronto`), mas **`pedidos` não conhece `notificacoes`** — a comunicação é via Django Signals, então dá pra remover/trocar o sistema de notificação sem tocar no app de pedidos.

---

## 2. Como rodar localmente

### Pré-requisitos
- Python 3.11+
- [PDM](https://pdm-project.org/latest/#installation) instalado

### Passo a passo

```bash
# 1. Instalar as dependências (cria o venv automaticamente)
pdm install

# 2. Copiar o arquivo de variáveis de ambiente de exemplo (se existir) e ajustar
cp .env.example .env    # se não existir .env.example, criar um .env com as variáveis da seção 3

# 3. Aplicar as migrations (cria o banco SQLite local)
pdm migrate

# 4. Popular o banco com dados de exemplo (categorias, produtos, promoções, usuários, pedidos)
pdm run python manage.py seed_dados

# 5. Rodar o servidor
pdm run python manage.py runserver
```

Depois disso, a API está em `http://127.0.0.1:8000/api/`.

### Credenciais criadas pelo `seed_dados`

| Papel | E-mail | Senha |
|---|---|---|
| Administração | `admin@cantina.ifc.edu.br` | `senha123` |
| Aluno | `joao@aluno.ifc.edu.br` | `senha123` |
| Aluno | `maria@aluno.ifc.edu.br` | `senha123` |
| Aluno | `pedro@aluno.ifc.edu.br` | `senha123` |

Rodar de novo é seguro (o comando pula o que já existe). Pra resetar os dados de exemplo: `pdm run python manage.py seed_dados --limpar`.

### Onde ver a API sem precisar de frontend

| URL | O que é |
|---|---|
| `/admin/` | Django Admin — CRUD manual de tudo, útil pra depurar dados |
| `/api/doc/` | Swagger UI — testa endpoints direto do navegador |
| `/api/schema/` | Schema OpenAPI cru (JSON) |

---

## 3. Variáveis de ambiente

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `SECRET_KEY` | produção | `django-insecure` (dev) | Chave secreta do Django |
| `DEBUG` | não | `True` | Modo debug |
| `DATABASE_URL` | produção | SQLite local | String de conexão (Postgres em produção) |
| `CLOUDINARY_URL` | não | vazio | Se ausente, upload de imagem cai pro disco local (`media/`) sem erro |
| `FRONTEND_URLS` | não | `http://localhost:5173,http://127.0.0.1:5173` | Origens liberadas no CORS/CSRF (endereços do frontend Vue) |
| `PEDIDO_TEMPO_LIMITE_RETIRADA_MINUTOS` | não | `15` | RN06 — minutos que um pedido pode ficar "pronto" antes do cancelamento automático |

---

## 4. Autenticação

JWT via `djangorestframework-simplejwt`. Login é por **e-mail**, não username.

| Endpoint | Método | Descrição |
|---|---|---|
| `/api/registro/` | `POST` | Cria uma conta de aluno (`email`, `name`, `password`) |
| `/api/token/` | `POST` | Login — recebe `email`+`password`, retorna `access` e `refresh` |
| `/api/token/refresh/` | `POST` | Troca o `refresh` por um novo `access` |
| `/api/token/verify/` | `POST` | Verifica se um token ainda é válido |

- **Access token**: expira em 3 horas.
- **Refresh token**: expira em 1 dia.

Todas as rotas abaixo (exceto leitura anônima quando indicado) exigem o header:
```
Authorization: Bearer <access_token>
```

### Papéis de usuário

Não existe um model separado de "papel". A diferenciação é pelo campo `is_staff` do `User`:
- `is_staff = True` → Administração da cantina.
- `is_staff = False` → Aluno.

Isso é decidido no Django Admin ou diretamente no banco — não existe endpoint público para um usuário virar admin sozinho (por design).

---

## 5. Endpoints por módulo

Todos usam paginação por página (`page`, `page_size`, resposta com `total_pages`/`results`) e podem ser filtrados via query params quando indicado.

### 5.1 Usuários (`core`)

| Endpoint | Método | Quem acessa | Descrição |
|---|---|---|---|
| `/api/usuarios/` | `GET` | autenticado | Lista usuários |
| `/api/usuarios/{id}/` | `GET` | autenticado | Detalhe de um usuário |

### 5.2 Catálogo (`catalogo`)

| Endpoint | Método | Quem acessa | Descrição |
|---|---|---|---|
| `/api/categorias/` | `GET` | qualquer autenticado | Lista categorias (filtro: `?ativa=true`) |
| `/api/categorias/` | `POST`/`PUT`/`DELETE` | admin | CRUD de categoria |
| `/api/produtos/` | `GET` | qualquer autenticado | Cardápio (filtros: `?categoria=`, `?ativo=`, `?destaque=`) — usa serializer enxuto, sem dado interno |
| `/api/produtos/{id}/` | `GET` | qualquer autenticado | Detalhe do produto (inclui descrição e estoque) |
| `/api/produtos/` | `POST`/`PUT`/`PATCH` | admin | Cadastro/edição — inclui `preco_custo` e `estoque_minimo`, nunca expostos ao aluno |
| `/api/promocoes/` | `GET` | qualquer autenticado | Lista promoções (filtro: `?produto=`) |
| `/api/promocoes/` | `POST`/`PUT`/`DELETE` | admin | CRUD de promoção — rejeita datas sobrepostas para o mesmo produto |
| `/api/produtos/mais_vendidos/` | `GET` | admin | Ranking por quantidade vendida (RF12). Query opcionais: `?data_inicio=`, `?data_fim=`, `?limite=` (padrão 10) |

**Importante:** o `ProdutoViewSet` troca de serializer conforme a ação (`ProdutoListSerializer` no `list`, `ProdutoWriteSerializer` no `create`/`update`, `ProdutoDetailSerializer` no resto) — por isso `preco_custo` nunca aparece em nenhuma resposta que o aluno recebe.

### 5.3 Pedidos (`pedidos`)

| Endpoint | Método | Quem acessa | Descrição |
|---|---|---|---|
| `/api/pedidos/` | `GET` | autenticado | Aluno vê só os próprios; admin vê todos (filtro: `?status=`) |
| `/api/pedidos/` | `POST` | autenticado | Cria pedido — body: `{"itens_criacao": [{"produto": id, "quantidade": n}, ...]}` |
| `/api/pedidos/{id}/` | `GET` | dono do pedido ou admin | Detalhe com itens e total |
| `/api/pedidos/{id}/alterar_status/` | `PATCH` | admin | Body: `{"status": "confirmado"}` — respeita a máquina de estados (RN04) |
| `/api/pedidos/{id}/qrcode/` | `GET` | dono do pedido ou admin | Retorna `{"codigo_retirada": "...", "qrcode_base64": "data:image/png;base64,..."}` |
| `/api/pedidos/retirar_via_qrcode/` | `POST` | admin | Body: `{"codigo_retirada": "..."}` — só funciona se o pedido estiver "pronto" |
| `/api/pedidos/relatorio_vendas/` | `GET` | admin | Query: `?data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD` — soma vendas de pedidos retirados no período |

**Máquina de estados do pedido (RN04):**

```
pendente → confirmado → pronto → retirado
   ↓            ↓          ↓
cancelado   cancelado  cancelado
```
Qualquer tentativa de pular etapa (ex: `pendente` → `pronto` direto) é rejeitada com erro 400.

### 5.4 Notificações (`notificacoes`)

| Endpoint | Método | Quem acessa | Descrição |
|---|---|---|---|
| `/api/notificacoes/` | `GET` | autenticado | Lista as próprias notificações (filtro: `?lida=false`) |
| `/api/notificacoes/{id}/marcar_lida/` | `PATCH` | autenticado (dono) | Marca uma notificação como lida |
| `/api/notificacoes/marcar_todas_lidas/` | `POST` | autenticado | Marca todas como lidas de uma vez |

Notificações são só leitura pela API — são criadas automaticamente pelo sistema (nunca pelo aluno ou admin diretamente), no momento em que um pedido passa para "pronto".

---

## 6. Regras de negócio implementadas (e onde estão no código)

| Regra | O que faz | Onde está |
|---|---|---|
| RN02 | Baixa automática de estoque ao criar o pedido | `PedidoSerializer.create()` |
| RN03 | Impede reservar produto sem estoque suficiente | `PedidoSerializer.validate_itens_criacao()` |
| RN04 | Só permite as transições de status previstas | `Pedido.pode_transicionar_para()` + `PedidoStatusUpdateSerializer` |
| RN05 | Só admin cadastra/edita promoção | `IsAdminOrReadOnly` (permissão) |
| RN06 | Cancela automaticamente pedido "pronto" há mais de X min, devolve estoque | comando `cancelar_pedidos_expirados` |
| RN07 | Pedido confirmado não pode ter itens alterados | não existe endpoint de editar itens após criação (garantido por ausência de funcionalidade, não por validação explícita) |

### QR Code de retirada
Cada pedido nasce com um `codigo_retirada` (UUID) — não é sequencial de propósito, pra ninguém adivinhar o código de outro aluno. O QR Code é gerado sob demanda (`/qrcode/`, biblioteca `qrcode`), nunca salvo como arquivo. A retirada (`/retirar_via_qrcode/`) reaproveita a mesma validação de transição de status da RN04, então só libera se o pedido estiver "pronto".

### Notificação de pedido pronto
Implementada via **Django Signal** (`pedidos/signals.py` → `pedido_ficou_pronto`), disparado dentro de `PedidoStatusUpdateSerializer.save()` quando o status muda para "pronto". O app `notificacoes` escuta esse signal (`notificacoes/receivers.py`) e cria o registro. É notificação "em app" via polling (o frontend consulta `GET /api/notificacoes/?lida=false` periodicamente) — não é push de verdade, porque isso exigiria Service Worker + Celery/Redis ou Django Channels, fora do escopo atual.

---

## 7. Comandos de management

| Comando | O que faz |
|---|---|
| `python manage.py seed_dados` | Popula categorias, produtos, promoções, usuários e pedidos de exemplo. Idempotente. Aceita `--limpar` |
| `python manage.py cancelar_pedidos_expirados` | RN06 — cancela pedidos "prontos" vencidos e devolve estoque. Pensado pra rodar via Cron Job periódico em produção (ainda não configurado — ver backlog) |
| `python manage.py graph_models -S -g -o core.png core` | Gera um diagrama automático dos models (roda sozinho depois de todo `pdm migrate`, configurado como `post_migrate` no `pyproject.toml`) |

---

## 8. Testes automatizados

```bash
pdm run python manage.py test
```

41 testes cobrindo: RN02 (baixa de estoque), RN03 (estoque insuficiente), RN04 (todas as transições de status válidas/inválidas), RN05 (permissão de promoção), RN06 (cancelamento automático + devolução de estoque), congelamento de preço no pedido, QR Code (gerar/retirar/retirar duas vezes/código inválido), notificação automática ao ficar pronto (e não duplicar), permissões (aluno não vê pedido/notificação de outro, não altera status, não cadastra produto/promoção), sobreposição de datas em promoção, `preco_custo` nunca aparecendo pro aluno, e os relatórios RF11/RF12 (cálculo correto, exige admin, período vazio não quebra).

Organizados em `pedidos/tests/` (`test_regras_negocio.py`, `test_qrcode_e_notificacao.py`, `test_rn06_cancelamento.py`, `test_relatorios.py`, com um `base.py` compartilhado) e `catalogo/tests.py`.

## 9. O que falta (visão rápida — detalhes no backlog de issues)

O núcleo funcional do backend está fechado: todas as regras de negócio da documentação (RN02–RN07) e todos os requisitos funcionais de relatório (RF11, RF12) estão implementados e testados. O que resta é **infraestrutura**, não lógica de negócio:

- Configuração real do Cloudinary em produção
- Deploy no Render (banco Postgres, variáveis de ambiente)
- Cron Job de produção pro `cancelar_pedidos_expirados` (o comando existe e funciona, só falta agendá-lo)
- Frontend (Vue) — ainda não iniciado, já existe protótipo visual de referência

---

## 10. Referência rápida de todos os endpoints

```
Autenticação
  POST   /api/registro/
  POST   /api/token/
  POST   /api/token/refresh/
  POST   /api/token/verify/

Usuários
  GET    /api/usuarios/
  GET    /api/usuarios/{id}/

Catálogo
  GET    /api/categorias/
  POST   /api/categorias/                        [admin]
  GET    /api/produtos/
  POST   /api/produtos/                           [admin]
  GET    /api/produtos/mais_vendidos/              [admin]
  GET    /api/promocoes/
  POST   /api/promocoes/                          [admin]

Pedidos
  GET    /api/pedidos/
  POST   /api/pedidos/
  GET    /api/pedidos/{id}/
  PATCH  /api/pedidos/{id}/alterar_status/        [admin]
  GET    /api/pedidos/{id}/qrcode/
  POST   /api/pedidos/retirar_via_qrcode/         [admin]
  GET    /api/pedidos/relatorio_vendas/           [admin]

Notificações
  GET    /api/notificacoes/
  PATCH  /api/notificacoes/{id}/marcar_lida/
  POST   /api/notificacoes/marcar_todas_lidas/
```

Lista completa e interativa sempre disponível em `/api/doc/`.