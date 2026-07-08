"""
Signal customizado disparado quando um pedido passa a ter status "pronto".

O app `pedidos` não conhece o app `notificacoes` (nem importa nada dele) —
quem escuta esse signal é responsabilidade de quem precisar reagir a ele.
Isso mantém os dois apps desacoplados: dá pra remover ou trocar o sistema de
notificações inteiro sem tocar em uma linha do app `pedidos`.
"""

import django.dispatch

# Enviado com kwargs: pedido (instância de Pedido)
pedido_ficou_pronto = django.dispatch.Signal()
