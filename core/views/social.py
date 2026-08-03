from django.conf import settings
from drf_spectacular.utils import extend_schema
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User

EMISSORES_VALIDOS_GOOGLE = ('accounts.google.com', 'https://accounts.google.com')


class GoogleLoginSerializer(serializers.Serializer):
    """Só documentação/validação de entrada — a verificação de verdade
    do token acontece na view, contra os servidores do Google."""

    credential = serializers.CharField(
        help_text='ID Token (JWT) devolvido pelo Google Identity Services no frontend.'
    )


class CustomGoogleLoginView(APIView):
    """Login/cadastro via Google.

    IMPORTANTE: isso espera o **ID Token** (o campo `credential` que o
    Google Identity Services devolve no callback do botão "Sign in with
    Google" no frontend) — não um *access token*.

    Por quê isso importa: um ID Token é um JWT assinado pelo Google que
    contém, entre outras coisas, o campo `aud` (audience) — o client_id
    de QUAL aplicação aquele token foi emitido para. Validamos a
    assinatura E conferimos que `aud` bate com o nosso GOOGLE_CLIENT_ID.

    Sem essa checagem de audiência (que é exatamente o que
    `id_token.verify_oauth2_token` faz), um token válido de QUALQUER
    aplicação Google — não só a nossa — seria aceito aqui, permitindo
    que alguém se autenticasse como outro usuário só possuindo um
    token do Google emitido para um app completamente diferente.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary='Login/cadastro via Google',
        description='Recebe o ID Token do Google Identity Services e retorna os tokens JWT da API.',
        request=GoogleLoginSerializer,
        responses={200: None, 400: None},
    )
    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['credential']

        if not settings.GOOGLE_CLIENT_ID:
            return Response(
                {'error': 'Login com Google não está configurado no servidor.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            info = id_token.verify_oauth2_token(token, google_requests.Request(), settings.GOOGLE_CLIENT_ID)
        except ValueError:
            return Response({'error': 'Token do Google inválido ou expirado.'}, status=status.HTTP_400_BAD_REQUEST)
        except GoogleAuthError:
            # Não conseguimos falar com os servidores do Google agora (rede,
            # timeout, etc.) — isso não é culpa de quem fez a requisição.
            return Response(
                {'error': 'Não foi possível verificar o login com o Google agora. Tente novamente.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if info.get('iss') not in EMISSORES_VALIDOS_GOOGLE:
            return Response({'error': 'Emissor do token inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        email = info.get('email')
        if not email:
            return Response(
                {'error': 'O Google não retornou um e-mail para essa conta.'}, status=status.HTTP_400_BAD_REQUEST
            )
        if not info.get('email_verified'):
            return Response(
                {'error': 'Esse e-mail ainda não foi verificado pelo Google.'}, status=status.HTTP_400_BAD_REQUEST
            )

        usuario, criado = User.objects.get_or_create(email=email, defaults={'name': info.get('name', '')})
        if criado:
            # Conta criada só via Google não tem senha — marca como
            # inutilizável em vez de deixar em branco (evita login por
            # senha vazia em qualquer brecha futura de autenticação).
            usuario.set_unusable_password()
            usuario.save(update_fields=['password'])

        refresh = RefreshToken.for_user(usuario)

        return Response({'access': str(refresh.access_token), 'refresh': str(refresh)}, status=status.HTTP_200_OK)
