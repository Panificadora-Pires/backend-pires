"""
Contrato dos provedores de resposta do chatbot.

Hoje o provedor é o de regras + FAQ (`chatbot.services.regras.ProvedorRegras`). Para plugar uma IA no
futuro, crie outra subclasse de `ProvedorResposta` e aponte `CHATBOT_PROVEDOR` para ela: a view e o
frontend continuam iguais, porque o formato de `Resposta` não muda.
"""

from dataclasses import asdict, dataclass, field

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass
class Resposta:
    intencao: str
    texto: str
    # Cada ação: {'tipo': 'intencao', 'rotulo', 'valor'}, {'tipo': 'chat', 'rotulo', 'pedido'}
    # ou {'tipo': 'rota', 'rotulo', 'rota'}.
    acoes: list = field(default_factory=list)
    pedidos: list = field(default_factory=list)
    produtos: list = field(default_factory=list)

    def como_dict(self):
        return asdict(self)


class ProvedorResposta:
    """Recebe o texto livre ou a intenção de um botão e devolve uma `Resposta`."""

    def responder(self, *, usuario, texto=None, intencao=None):
        raise NotImplementedError


def obter_provedor():
    return import_string(settings.CHATBOT_PROVEDOR)()
