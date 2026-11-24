from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
    TokenVerifySerializer,
)
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)


class VerifiedEmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Só emite JWT para contas com e-mail confirmado."""

    def validate(self, attrs):
        data = super().validate(attrs)

        if not self.user.email_verified:
            raise AuthenticationFailed(
                'Confirme seu e-mail antes de entrar.',
                code='email_not_verified',
            )

        return data


@extend_schema_view(
    post=extend_schema(
        summary='Obter token JWT',
        description=(
            'Autentica com e-mail e senha. '
            'A conta precisa estar ativa e com e-mail confirmado.'
        ),
        request=VerifiedEmailTokenObtainPairSerializer,
        responses={200: VerifiedEmailTokenObtainPairSerializer, 401: None},
    )
)
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = VerifiedEmailTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class RevokeAwareTokenRefreshSerializer(TokenRefreshSerializer):
    """Recusa renovar refresh de conta apagada ou emitido antes de uma troca de senha.

    O SimpleJWT só confere a revogação (CHECK_REVOKE_TOKEN) ao autenticar com o access;
    sem esta checagem, um refresh antigo seguiria rotacionando tokens inúteis.
    """

    def validate(self, attrs):
        try:
            refresh = self.token_class(attrs['refresh'])
        except TokenError as exc:
            raise AuthenticationFailed(str(exc), code='token_not_valid') from exc

        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        user = get_user_model().objects.filter(**{api_settings.USER_ID_FIELD: user_id}).first()
        if user is None:
            raise AuthenticationFailed('Sessão inválida. Entre novamente.', code='user_not_found')
        if api_settings.CHECK_REVOKE_TOKEN and refresh.payload.get(
            api_settings.REVOKE_TOKEN_CLAIM
        ) != get_md5_hash_password(user.password):
            raise AuthenticationFailed('A senha da conta foi alterada. Entre novamente.', code='password_changed')

        return super().validate(attrs)


@extend_schema_view(
    post=extend_schema(
        summary='Atualizar token JWT',
        description='Rotaciona o refresh token e retorna um novo access token.',
        request=RevokeAwareTokenRefreshSerializer,
        responses={200: RevokeAwareTokenRefreshSerializer, 401: None},
    )
)
class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = RevokeAwareTokenRefreshSerializer


@extend_schema_view(
    post=extend_schema(
        summary='Verificar token JWT',
        description='Verifica se um token JWT access ou refresh é válido.',
        request=TokenVerifySerializer,
        responses={200: None, 401: None},
    )
)
class CustomTokenVerifyView(TokenVerifyView):
    pass


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(trim_whitespace=True)


class LogoutView(APIView):
    """Revoga o refresh token apresentado pelo cliente."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'logout'

    @extend_schema(
        summary='Encerrar sessão',
        request=LogoutSerializer,
        responses={204: None, 400: None},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            token.blacklist()
        except TokenError:
            return Response(
                {'error': 'Refresh token inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
