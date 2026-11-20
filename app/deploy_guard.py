"""Fail-closed para configuração mínima do banco em ambiente sem DEBUG.

Sem rede, sem acesso a secrets e sem efeitos colaterais.
O ambiente de desenvolvimento continua podendo usar SQLite com DEBUG=True.
"""

def exigir_banco_de_producao(*, debug: bool, database_url: str) -> None:
    """Impede inicialização sem PostgreSQL quando DEBUG está desativado."""
    if debug:
        return

    url = (database_url or "").strip().lower()
    if not url:
        raise RuntimeError(
            "DATABASE_URL é obrigatória quando DEBUG=False. "
            "Configure o PostgreSQL de produção antes de iniciar."
        )
    if not url.startswith(("postgres://", "postgresql://")):
        raise RuntimeError(
            "Quando DEBUG=False, DATABASE_URL precisa apontar para PostgreSQL. "
            "SQLite e outros bancos não são permitidos nesse ambiente."
        )
