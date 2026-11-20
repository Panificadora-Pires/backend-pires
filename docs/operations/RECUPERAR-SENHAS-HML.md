# Recuperar senhas das tres contas ficticias (somente HML)

**Escopo:** app Fabroku `backend-pires-hml` + PostgreSQL Neon HML, sem afetar a producao `backend-pires`. Este procedimento **redefine** senhas; nao recupera senhas antigas nem remove contas, pedidos ou chat.

**Pre-requisito:** revisar/aprovar e integrar o PR de recuperacao na branch **`deploy/pr6-hml-asgi`**, nunca em `dev` ou `main`, e fazer redeploy **manual somente da app HML** para instalar o novo management command. Nao executar no banco real.

## 1. Gerar tres senhas novas privadas

No PowerShell local (com Python instalado):

```powershell
1..3 | ForEach-Object { python -c "import secrets; print(secrets.token_urlsafe(32))" }
```

Guarde os tres valores em um gerenciador de senhas, na ordem: Administrador, Cliente A, Cliente B. Nao poste as senhas em chats, GitHub, capturas de tela ou logs; nao use senhas de exemplo dos testes.

## 2. Configuracao temporaria somente no Fabroku HML

No painel privado de **`backend-pires-hml`** configure:

```dotenv
HML_REDEFINICAO_AUTORIZADA=SIM
HML_NOVA_SENHA_ADMIN=<PRIMEIRA_SENHA>
HML_NOVA_SENHA_CLIENTE_A=<SEGUNDA_SENHA>
HML_NOVA_SENHA_CLIENTE_B=<TERCEIRA_SENHA>
```

Confirme antes que `ALLOWED_HOSTS` contem `backend-pires-hml.class.fabricadesoftware.ifc.edu.br` e que `DATABASE_URL` segue apontando para **Neon HML**, nunca para o banco da producao. Nao troque `DATABASE_URL` ou `REDIS_URL`.

## 3. Deploy e execucao

Apos integrar a branch de recuperacao em `deploy/pr6-hml-asgi`, fazer **Redeploy manual somente do app HML** no Fabroku; reiniciar sem redeploy pode nao instalar o comando novo.

Quando a aplicacao estiver `Running` e `/api/health/` responder, executar no console de comandos da **HML**:

```text
python manage.py redefinir_senhas_hml
```

O comando:
- recusa host diferente de HML ou banco fora de `.neon.tech`;
- exige opt-in temporario explicito;
- valida as tres novas senhas (minimo 20 caracteres e validadores Django) e exige valores distintos;
- exige que as tres contas ja existam;
- altera **somente** os hashes de senha em transacao atomica;
- nao imprime senhas ou altera perfis, pedidos, mensagens ou permissoes.

O sucesso informa apenas `Tres senhas HML redefinidas com sucesso.`

## 4. Validar e limpar

- Testar login independente para:
  - admin.hml@pires.invalid
  - cliente-a.hml@pires.invalid
  - cliente-b.hml@pires.invalid
- Encerrar sessoes antigas; tokens JWT emitidos antes da troca podem continuar validos ate expirar, conforme configuracao.
- **Remover as quatro variaveis temporarias** `HML_REDEFINICAO_AUTORIZADA` e `HML_NOVA_SENHA_*` do Fabroku HML e confirmar reinicio/redeploy se necessario. A exclusao nao reverte os novos hashes.
- Manter `dev`, `main`, `backend-pires` (producao), o Redis HML e os dados das contas intactos.

Se ocorrer erro, nao recriar contas nem resetar banco: verificar ambiente, versao deployada e mensagem do comando sem compartilhar segredos.
