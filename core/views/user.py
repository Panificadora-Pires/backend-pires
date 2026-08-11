import logging
import smtplib

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    IsAdminUser,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from core.models import User, VerificationCode
from core.serializers import (
    UserRegistrationSerializer,
    UserSerializer,
)
from core.services import (
    issue_challenge,
    invalidate_challenge,
    send_account_activation_email,
)

logger = logging.getLogger(__name__)


class UserViewSet(ReadOnlyModelViewSet):
    """
    Consulta de usuários.

    Usuários comuns acessam somente /usuarios/me/.
    Administradores podem listar e consultar usuários.
    """

    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'me':
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdminUser]

        return [
            permission()
            for permission in permission_classes
        ]

    @extend_schema(
        summary='Dados do usuário autenticado',
        description='Retorna os dados do usuário autenticado.',
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


class UserRegistrationView(APIView):
    """Cadastro público com ativação obrigatória por e-mail."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'registration'

    @extend_schema(
        summary='Registro de novo usuário',
        description=(
            'Cria uma conta inativa e envia um código '
            'de confirmação para o e-mail cadastrado.'
        ),
        request=UserRegistrationSerializer,
        responses={
            201: None,
            400: None,
        },
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        user = serializer.save()

        issued = issue_challenge(
            user=user,
            purpose=(
                VerificationCode.Purpose.ACCOUNT_ACTIVATION
            ),
        )

        email_sent = True

        try:
            send_account_activation_email(
                user=user,
                code=issued.code,
            )
        except (smtplib.SMTPException, OSError):
            email_sent = False
            invalidate_challenge(issued.challenge)
            logger.exception(
                'Falha ao enviar e-mail de ativação para user_id=%s.',
                user.pk,
            )

        message = (
            'Cadastro realizado. Enviamos um código de confirmação '
            'para o seu e-mail.'
            if email_sent
            else (
                'Cadastro realizado, mas não foi possível enviar '
                'o e-mail agora. Solicite um novo código.'
            )
        )

        return Response(
            {
                'message': message,
                'verification_id': str(
                    issued.challenge.public_id
                ),
                'expires_in_seconds': (
                    settings.VERIFICATION_CODE_TTL_MINUTES * 60
                ),
                'email_sent': email_sent,
            },
            status=status.HTTP_201_CREATED,
        )
