import logging
import smtplib

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import (
    AllowAny,
    IsAdminUser,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers.invite import (
    AdminInviteCreateSerializer,
    AdminInviteRegistrationSerializer,
)

logger = logging.getLogger(__name__)


class AdminInviteCreateView(APIView):
    """Criação de convites para administradores."""

    permission_classes = [
        IsAdminUser,
    ]

    @extend_schema(
        request=AdminInviteCreateSerializer,
        responses={
            201: AdminInviteCreateSerializer,
            400: None,
            401: None,
            403: None,
            503: None,
        },
    )
    def post(self, request):
        serializer = AdminInviteCreateSerializer(
            data=request.data,
            context={
                'request': request,
            },
        )
        serializer.is_valid(
            raise_exception=True,
        )

        try:  # ruff: ignore[too-many-statements-in-try-clause]
            with transaction.atomic():
                invite = serializer.save()
                token_str = str(invite.token)

                quantidade_enviada = send_mail(
                    subject=(
                        'Convite - Pires Panificadora Admin'
                    ),
                    message=(
                        'Você foi convidado para ser '
                        'administrador da Pires Panificadora.\n\n'
                        f'Token de cadastro: {token_str}\n\n'
                        'Este convite expira em 48 horas.'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[
                        invite.email,
                    ],
                    fail_silently=False,
                )

                if quantidade_enviada != 1:
                    raise OSError(
                        'O backend de e-mail não confirmou '
                        'o envio da mensagem.'
                    )

        except (
            smtplib.SMTPException,
            OSError,
        ):
            logger.exception(
                'Falha ao enviar convite administrativo.'
            )

            return Response(
                {
                    'error': (
                        'Não foi possível enviar o convite '
                        'por e-mail. Tente novamente.'
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = {
            'message': (
                'Convite criado e enviado com sucesso.'
            ),
            'email': invite.email,
        }

        if settings.DEBUG:
            payload['token'] = token_str

        return Response(
            payload,
            status=status.HTTP_201_CREATED,
        )


class AdminInviteRegistrationView(APIView):
    """Cadastro público utilizando um convite válido."""

    permission_classes = [
        AllowAny,
    ]

    @extend_schema(
        request=AdminInviteRegistrationSerializer,
        responses={
            201: None,
            400: None,
        },
    )
    def post(self, request):
        serializer = AdminInviteRegistrationSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        user = serializer.save()

        return Response(
            {
                'message': (
                    'Administrador registrado com sucesso.'
                ),
                'email': user.email,
            },
            status=status.HTTP_201_CREATED,
        )
