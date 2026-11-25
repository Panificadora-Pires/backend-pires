"""
Signals do chat por pedido.

O app `chat` não conhece o app `notificacoes`: quem quiser reagir a uma mensagem
(por exemplo, avisar o cliente) escuta estes signals.
"""

import django.dispatch

mensagem_da_padaria_enviada = django.dispatch.Signal()

chat_lido_pelo_cliente = django.dispatch.Signal()
