"""
Classes de permissão customizadas para diferenciar Aluno de Administrador.

A distinção usa o campo `is_staff`, já existente no model User do template:
- is_staff=True  -> Administrador da cantina
- is_staff=False -> Aluno
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrReadOnly(BasePermission):
    """Leitura liberada a qualquer usuário autenticado; escrita só para a administração.

    Usado em Produto e Promocao: qualquer aluno pode ver o cardápio e as
    promoções (RF09), mas só a administração pode cadastrar ou alterar (RF02,
    RF03, RN05).
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff


class IsOwnerOrAdmin(BasePermission):
    """Permite acesso ao dono do pedido ou à administração (RF10).

    Usado em Pedido: o aluno só acessa seus próprios pedidos, a administração
    acessa todos.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.usuario_id == request.user.id
