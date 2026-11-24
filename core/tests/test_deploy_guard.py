"""PR7A: controles de configuração de produção, sem acesso a bancos reais."""
from django.test import SimpleTestCase

from app.deploy_guard import exigir_banco_de_producao


class BancoDeProducaoTests(SimpleTestCase):
    def test_desenvolvimento_sqlite_permitido(self):
        exigir_banco_de_producao(debug=True, database_url="sqlite:///db.sqlite3")

    def test_sem_banco_em_producao_rejeitado(self):
        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL é obrigatória"):
            exigir_banco_de_producao(debug=False, database_url="")

    def test_espacos_nao_contam_como_banco(self):
        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL é obrigatória"):
            exigir_banco_de_producao(debug=False, database_url="  ")

    def test_sqlite_nao_pode_ser_banco_de_producao(self):
        with self.assertRaisesRegex(RuntimeError, "precisa apontar para PostgreSQL"):
            exigir_banco_de_producao(debug=False, database_url="sqlite:///db.sqlite3")

    def test_mysql_nao_pode_ser_banco_de_producao(self):
        with self.assertRaisesRegex(RuntimeError, "precisa apontar para PostgreSQL"):
            exigir_banco_de_producao(
                debug=False, database_url="mysql://user:password@example.invalid/db"
            )

    def test_postgres_aceito_sem_abrir_conexao(self):
        for url in (
            "postgresql://user:password@example.invalid:5432/db",
            "postgres://user:password@example.invalid/db",
        ):
            with self.subTest(scheme=url.split(":")[0]):
                exigir_banco_de_producao(debug=False, database_url=url)
