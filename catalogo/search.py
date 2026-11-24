"""Busca literal tolerante a acentos para os catálogos administrativos.

Usa regex parametrizada e caracteres escapados, compatível com SQLite e
PostgreSQL sem exigir a extensão unaccent no banco.
"""
import re
import unicodedata

_ACENTOS = {
    'a': 'aáàâãä', 'e': 'eéèêë', 'i': 'iíìîï',
    'o': 'oóòôõö', 'u': 'uúùûü', 'c': 'cç',
    'n': 'nñ',
}


def buscar_sem_acentos(texto):
    sem_acentos = ''.join(
        letra for letra in unicodedata.normalize('NFD', texto)
        if not unicodedata.combining(letra)
    )
    return ''.join(
        f"[{_ACENTOS[letra.lower()]}]" if letra.lower() in _ACENTOS
        else re.escape(letra)
        for letra in sem_acentos
    )
