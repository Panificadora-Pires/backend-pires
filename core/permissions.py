"""
Permissões personalizadas do sistema.
"""

from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
)


class IsAdminOrReadOnly(BasePermission):
    """
    Usuários autenticados podem consultar.

    Somente administradores podem criar, alterar
    ou excluir registros.
    """

    def has_permission(self, request, view):
        if not (
            request.user
            and request.user.is_authenticated
        ):
            return False

        if request.method in SAFE_METHODS:
            return True

        return request.user.is_staff


class IsOwnerOrAdmin(BasePermission):
    """
    Permite acesso ao proprietário do objeto
    ou a um administrador.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
        )

    def has_object_permission(
        self,
        request,
        view,
        obj,
    ):
        if request.user.is_staff:
            return True

        return (
            obj.usuario_id
            == request.user.id
        )
