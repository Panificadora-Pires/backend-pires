from django.conf import settings
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

    @extend_schema(request=AdminInviteCreateSerializer, responses={201: AdminInviteCreateSerializer})
    def post(self, request):
        serializer = AdminInviteCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        invite = serializer.save()
        token_str = str(invite.token)

        # fail_silently=True porque, sem EMAIL_BACKEND real configurado em
        # produção, isso não deve derrubar a criação do convite — o admin
        # só não vai conseguir avisar o convidado por e-mail nesse caso.
        send_mail(
            subject='Convite - Pires Panificadora Admin',
            message=f'Você foi convidado a ser administrador! Use este token para se registrar: {token_str}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invite.email],
            fail_silently=True,
        )

        payload = {'message': 'Convite criado com sucesso. Um e-mail foi enviado ao convidado.', 'email': invite.email}

        # O token só entra na resposta em DEBUG (ambiente local), pra
        # facilitar teste sem precisar configurar e-mail de verdade. Em
        # produção ele NUNCA deve trafegar em uma resposta de API — quem
        # o recebe é o convidado, por e-mail, e mais ninguém.
        if settings.DEBUG:
            payload['token'] = token_str

        return Response(payload, status=status.HTTP_201_CREATED)


class AdminInviteRegistrationView(APIView):
    """Endpoint público para o convidado se registrar usando o token."""

    permission_classes = [AllowAny]

    @extend_schema(request=AdminInviteRegistrationSerializer, responses={201: None})
    def post(self, request):
        serializer = AdminInviteRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {'message': 'Administrador registrado com sucesso.', 'email': user.email},
            status=status.HTTP_201_CREATED,
        )
