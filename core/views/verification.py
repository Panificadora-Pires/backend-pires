import logging
import smtplib
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.crypto import salted_hmac
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.models import User, VerificationCode
from core.serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ResendActivationSerializer,
    VerificationCodeSerializer,
)
from core.services import (
    InvalidVerificationCode,
    activate_account,
    issue_or_reuse_challenge,
    invalidate_challenge,
    reset_password,
    send_account_activation_email,
    send_password_reset_email,
)

logger = logging.getLogger(__name__)

GENERIC_RESET_MESSAGE = (
    'Se existir uma conta elegível para esse e-mail, '
    'enviaremos um código de recuperação.'
)

GENERIC_RESEND_MESSAGE = (
    'Se existir uma conta aguardando confirmação, '
    'enviaremos um código para o e-mail informado.'
)

INVALID_CODE_MESSAGE = 'Código inválido, expirado ou já utilizado.'

EMAIL_DELIVERY_EXCEPTIONS = (
    smtplib.SMTPException,
    OSError,
)


def _placeholder_request_id(*, email, purpose):
    """Gera UUID opaco estável durante o cooldown para evitar enumeração.

    Uma conta inexistente recebe um identificador com o mesmo padrão temporal
    de uma conta real durante o período de cooldown. Assim, chamadas repetidas
    não revelam existência da conta apenas comparando o campo verification_id.
    """

    cooldown = max(
        1,
        settings.VERIFICATION_RESEND_COOLDOWN_SECONDS,
    )
    bucket = int(timezone.now().timestamp()) // cooldown
    digest = salted_hmac(
        'core.verification-placeholder',
        f'{purpose}:{email.casefold()}:{bucket}',
        secret=settings.SECRET_KEY,
        algorithm='sha256',
    ).hexdigest()

    return str(uuid.UUID(digest[:32]))


class AccountActivationConfirmView(APIView):
    """Confirma o código de ativação da conta."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'verification_confirm'

    @extend_schema(
        summary='Confirmar cadastro',
        request=VerificationCodeSerializer,
        responses={200: None, 400: None},
    )
    def post(self, request):
        serializer = VerificationCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            activate_account(
                public_id=serializer.validated_data['request_id'],
                code=serializer.validated_data['code'],
            )
        except InvalidVerificationCode:
            return Response(
                {'error': INVALID_CODE_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {'message': 'E-mail confirmado. Sua conta foi ativada.'},
            status=status.HTTP_200_OK,
        )


class AccountActivationResendView(APIView):
    """Reenvia o código de ativação sem enumerar contas."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'verification_send'

    @extend_schema(
        summary='Reenviar código de confirmação',
        request=ResendActivationSerializer,
        responses={202: None},
    )
    def post(self, request):
        serializer = ResendActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        purpose = VerificationCode.Purpose.ACCOUNT_ACTIVATION
        request_id = _placeholder_request_id(
            email=email,
            purpose=purpose,
        )
        retry_after = settings.VERIFICATION_RESEND_COOLDOWN_SECONDS

        user = User.objects.filter(
            email__iexact=email,
            email_verified=False,
            is_active=False,
        ).first()

        if user is not None:
            issued = issue_or_reuse_challenge(
                user=user,
                purpose=purpose,
            )
            request_id = str(issued.challenge.public_id)

            if issued.should_send_email:
                try:
                    send_account_activation_email(
                        user=user,
                        code=issued.code,
                    )
                except EMAIL_DELIVERY_EXCEPTIONS:
                    invalidate_challenge(issued.challenge)
                    logger.exception(
                        'Falha ao reenviar ativação para user_id=%s.',
                        user.pk,
                    )

        return Response(
            {
                'message': GENERIC_RESEND_MESSAGE,
                'verification_id': request_id,
                'retry_after_seconds': retry_after,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetRequestView(APIView):
    """Solicita código de redefinição sem revelar se a conta existe."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    @extend_schema(
        summary='Solicitar recuperação de senha',
        request=PasswordResetRequestSerializer,
        responses={202: None},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        purpose = VerificationCode.Purpose.PASSWORD_RESET
        request_id = _placeholder_request_id(
            email=email,
            purpose=purpose,
        )
        retry_after = settings.VERIFICATION_RESEND_COOLDOWN_SECONDS

        user = User.objects.filter(
            email__iexact=email,
            email_verified=True,
            is_active=True,
        ).first()

        if user is not None:
            issued = issue_or_reuse_challenge(
                user=user,
                purpose=purpose,
            )
            request_id = str(issued.challenge.public_id)

            if issued.should_send_email:
                try:
                    send_password_reset_email(
                        user=user,
                        code=issued.code,
                    )
                except EMAIL_DELIVERY_EXCEPTIONS:
                    invalidate_challenge(issued.challenge)
                    logger.exception(
                        'Falha ao enviar recuperação para user_id=%s.',
                        user.pk,
                    )

        return Response(
            {
                'message': GENERIC_RESET_MESSAGE,
                'verification_id': request_id,
                'retry_after_seconds': retry_after,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetConfirmView(APIView):
    """Confirma o código e redefine a senha."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'verification_confirm'

    @extend_schema(
        summary='Redefinir senha',
        request=PasswordResetConfirmSerializer,
        responses={200: None, 400: None},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            reset_password(
                public_id=serializer.validated_data['request_id'],
                code=serializer.validated_data['code'],
                new_password=serializer.validated_data['new_password'],
            )
        except InvalidVerificationCode:
            return Response(
                {'error': INVALID_CODE_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoValidationError as exc:
            return Response(
                {'new_password': list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                'message': (
                    'Senha redefinida com sucesso. '
                    'Faça login novamente.'
                )
            },
            status=status.HTTP_200_OK,
        )
