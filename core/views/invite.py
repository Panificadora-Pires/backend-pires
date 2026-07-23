from django.conf import settings

# Importações de email (para enviar o convite)
from django.core.mail import send_mail
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers.invite import AdminInviteCreateSerializer, AdminInviteRegistrationSerializer


class AdminInviteCreateView(APIView):
    """Endpoint para Admins criarem convites para outros Admins."""
    permission_classes = [IsAdminUser]

    @extend_schema(
        request=AdminInviteCreateSerializer,
        responses={201: AdminInviteCreateSerializer}
    )
    def post(self, request):
        serializer = AdminInviteCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            invite = serializer.save()

            # TODO: Em produção, configurar SMTP no settings.py para enviar email real
            # Aqui estamos apenas simulando o envio e retornando o token para testes no frontend
            token_str = str(invite.token)

            # Simulação de Email (aparece no console se EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend')  # ruff:ignore[line-too-long]
            try:
                send_mail(
                    subject='Convite - Pires Panificadora Admin',
                    message=f'Você foi convidado! Use este token para se registrar: {token_str}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[invite.email],
                    fail_silently=True,
                )
            except Exception:
                pass

            return Response({
                'message': 'Convite criado com sucesso.',
                'token': token_str,  # Retornamos para facilitar o teste no frontend
                'email': invite.email
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminInviteRegistrationView(APIView):
    """Endpoint público para o convidado se registrar usando o token."""
    permission_classes = [AllowAny]

    @extend_schema(
        request=AdminInviteRegistrationSerializer,
        responses={201: None}
    )
    def post(self, request):
        serializer = AdminInviteRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'message': 'Administrador registrado com sucesso.',
                'email': user.email
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
