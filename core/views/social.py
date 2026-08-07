from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User, VerificationCode

EMISSORES_VALIDOS_GOOGLE = (
    'accounts.google.com',
    'https://accounts.google.com',
)


class GoogleLoginSerializer(serializers.Serializer):
    """Entrada do endpoint de login Google."""

    credential = serializers.CharField(
        trim_whitespace=True,
        allow_blank=False,
        help_text=(
            'ID Token devolvido pelo Google Identity Services '
            'no campo credential.'
        ),
    )


class GoogleLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class GoogleLoginErrorSerializer(serializers.Serializer):
    error = serializers.CharField()


class CustomGoogleLoginView(APIView):
    """Login e cadastro utilizando uma conta Google."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'google_login'

    @extend_schema(
        summary='Login/cadastro via Google',
        description=(
            'Valida o ID Token do Google, vincula a identidade '
            'e retorna tokens JWT da API.'
        ),
        request=GoogleLoginSerializer,
        responses={
            200: GoogleLoginResponseSerializer,
            400: GoogleLoginErrorSerializer,
            403: GoogleLoginErrorSerializer,
            409: GoogleLoginErrorSerializer,
            503: GoogleLoginErrorSerializer,
        },
    )
    def post(self, request):
        serializer = GoogleLoginSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        if not settings.GOOGLE_CLIENT_ID:
            return Response(
                {
                    'error': (
                        'Login com Google não está configurado '
                        'no servidor.'
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            info = id_token.verify_oauth2_token(
                serializer.validated_data['credential'],
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError:
            return Response(
                {'error': 'Token do Google inválido ou expirado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except GoogleAuthError:
            return Response(
                {
                    'error': (
                        'Não foi possível verificar o login '
                        'com o Google agora. Tente novamente.'
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if info.get('iss') not in EMISSORES_VALIDOS_GOOGLE:
            return Response(
                {'error': 'Emissor do token Google inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        google_sub = str(
            info.get('sub') or ''
        ).strip()
        email = str(
            info.get('email') or ''
        ).strip().lower()
        nome = str(
            info.get('name') or ''
        ).strip()

        if not google_sub:
            return Response(
                {
                    'error': (
                        'O Google não retornou um identificador '
                        'válido para esta conta.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not email:
            return Response(
                {
                    'error': (
                        'O Google não retornou um endereço '
                        'de e-mail para esta conta.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not info.get('email_verified'):
            return Response(
                {
                    'error': (
                        'O endereço de e-mail ainda não foi '
                        'verificado pelo Google.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                usuario = (
                    User.objects
                    .select_for_update()
                    .filter(google_sub=google_sub)
                    .first()
                )

                if usuario is not None:
                    if not usuario.is_active:
                        return Response(
                            {'error': 'Esta conta está desativada.'},
                            status=status.HTTP_403_FORBIDDEN,
                        )

                    campos_atualizados = []

                    if usuario.email.casefold() != email.casefold():
                        conflito = User.objects.filter(
                            email__iexact=email,
                        ).exclude(pk=usuario.pk).exists()

                        if conflito:
                            return Response(
                                {
                                    'error': (
                                        'O e-mail atual desta conta Google '
                                        'já está associado a outro cadastro.'
                                    )
                                },
                                status=status.HTTP_409_CONFLICT,
                            )

                        usuario.email = email
                        campos_atualizados.append('email')

                    if not usuario.email_verified:
                        usuario.email_verified = True
                        campos_atualizados.append('email_verified')

                    if not usuario.name and nome:
                        usuario.name = nome
                        campos_atualizados.append('name')

                    if campos_atualizados:
                        usuario.save(
                            update_fields=campos_atualizados,
                        )

                else:
                    usuario = (
                        User.objects
                        .select_for_update()
                        .filter(email__iexact=email)
                        .first()
                    )

                    if usuario is not None:
                        if (
                            usuario.google_sub
                            and usuario.google_sub != google_sub
                        ):
                            return Response(
                                {
                                    'error': (
                                        'Este e-mail já está vinculado '
                                        'a outra conta Google.'
                                    )
                                },
                                status=status.HTTP_409_CONFLICT,
                            )

                        # Uma conta já verificada e inativa representa
                        # suspensão administrativa e não deve ser reativada.
                        if (
                            usuario.email_verified
                            and not usuario.is_active
                        ):
                            return Response(
                                {'error': 'Esta conta está desativada.'},
                                status=status.HTTP_403_FORBIDDEN,
                            )

                        campos_atualizados = []

                        if not usuario.google_sub:
                            usuario.google_sub = google_sub
                            campos_atualizados.append('google_sub')

                        if not usuario.email_verified:
                            usuario.email_verified = True
                            campos_atualizados.append('email_verified')

                        if not usuario.is_active:
                            usuario.is_active = True
                            campos_atualizados.append('is_active')

                        if not usuario.name and nome:
                            usuario.name = nome
                            campos_atualizados.append('name')

                        if campos_atualizados:
                            usuario.save(
                                update_fields=campos_atualizados,
                            )

                    else:
                        usuario = User.objects.create_user(
                            email=email,
                            password=None,
                            name=nome,
                            google_sub=google_sub,
                            email_verified=True,
                            is_active=True,
                        )

                VerificationCode.objects.filter(
                    user=usuario,
                    purpose=(
                        VerificationCode.Purpose.ACCOUNT_ACTIVATION
                    ),
                    used_at__isnull=True,
                ).update(
                    used_at=timezone.now(),
                )

        except IntegrityError:
            return Response(
                {
                    'error': (
                        'Não foi possível vincular a conta Google '
                        'porque já existe um cadastro conflitante.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        refresh = RefreshToken.for_user(usuario)

        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
            status=status.HTTP_200_OK,
        )
