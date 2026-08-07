from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import (
    AllowAny,
    IsAdminUser,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from core.models import User
from core.serializers import (
    UserRegistrationSerializer,
    UserSerializer,
)


class UserViewSet(ReadOnlyModelViewSet):
    """
    Consulta de usuários.

    Usuários comuns acessam somente /usuarios/me/.
    Administradores podem listar e consultar usuários.

    Criação, alteração e exclusão ficam no Django Admin.
    """

    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'me':
            permission_classes = [
                IsAuthenticated,
            ]
        else:
            permission_classes = [
                IsAdminUser,
            ]

        return [
            permission()
            for permission in permission_classes
        ]

    @extend_schema(
        summary='Dados do usuário autenticado',
        description=(
            'Retorna os dados do usuário autenticado.'
        ),
        responses={
            200: UserSerializer,
            401: None,
        },
    )
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated],
    )
    def me(self, request):
        serializer = self.get_serializer(
            request.user,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary='Registro de novo usuário',
    description=(
        'Cria um novo usuário comum no sistema. '
        'Não requer autenticação.'
    ),
    request=UserRegistrationSerializer,
    responses={
        201: UserRegistrationSerializer,
        400: None,
    },
)
class UserRegistrationView(CreateAPIView):
    """Endpoint público para cadastro de usuários."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
