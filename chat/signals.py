"""
Signals do chat por pedido.

O app `chat` não conhece o app `notificacoes`: quem quiser reagir a uma mensagem
(por exemplo, avisar o cliente) escuta estes signals.
"""

import django.dispatch

# Enviado com kwargs: mensagem (instância de Mensagem) e pedido (instância de Pedido)
mensagem_da_padaria_enviada = django.dispatch.Signal()

# Enviado com kwargs: pedido (instância de Pedido) e leitor (usuário dono do pedido)
chat_lido_pelo_cliente = django.dispatch.Signal()
