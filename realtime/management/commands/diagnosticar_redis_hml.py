"""Diagnóstico seguro do Redis exclusivamente na branch de homologação.

Executar pelo console Fabroku: python manage.py diagnosticar_redis_hml
Não imprime host, usuário, senha, URL nem o conteúdo de chaves externas.
"""
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Verifica PING, versão (quando permitida) e GETDEL atômico do Redis HML sem expor credenciais."

    def handle(self, *args, **options):
        import redis

        endereco = settings.REALTIME_REDIS_URL
        if not endereco or not endereco.startswith(("redis://", "rediss://", "unix://")):
            raise CommandError("Redis HML não configurado. Verifique apenas a existência de REDIS_URL.")

        cliente = redis.Redis.from_url(
            endereco,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        chave = f"pires:hml:diagnostico:{secrets.token_hex(16)}"

        try:
            cliente.ping()
            self.stdout.write(self.style.SUCCESS("Redis PING: OK"))

            try:
                versao = cliente.info("server").get("redis_version", "não informada")
            except redis.RedisError:
                versao = "não disponível (INFO restrito)"
            self.stdout.write(f"Versão Redis: {versao}")

            # Uma chave randômica com TTL, sem tocar em dados reais ou tickets.
            if not cliente.set(chave, "hml", ex=30, nx=True):
                raise CommandError("Não foi possível reservar a chave temporária.")
            valor = cliente.getdel(chave)
            repeticao = cliente.getdel(chave)
            if valor != "hml" or repeticao is not None:
                raise CommandError("GETDEL não confirmou remoção de uso único.")
            self.stdout.write(self.style.SUCCESS("GETDEL atômico: OK"))
            self.stdout.write(self.style.SUCCESS("Redis HML: PRONTO para o próximo gate"))
        except redis.RedisError:
            # Redis pode incluir dados internos no texto das exceções.
            raise CommandError(
                "Falha de conectividade ou comando Redis. Verifique vínculo, serviço e versão."
            ) from None
        finally:
            try:
                cliente.delete(chave)
                cliente.close()
            except redis.RedisError:
                pass
