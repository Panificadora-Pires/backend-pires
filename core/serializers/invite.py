from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from core.models import AdminInvite, User


class AdminInviteCreateSerializer(
    serializers.ModelSerializer
):
    """Criação ou renovação de convite administrativo."""

    class Meta:
        model = AdminInvite
        fields = [
            'email',
        ]

    def validate_email(self, value):
        email = User.objects.normalize_email(
            value,
        ).strip().lower()

        if User.objects.filter(
            email__iexact=email,
        ).exists():
            raise serializers.ValidationError(
                'Já existe um usuário com este e-mail.'
            )

        return email

    def create(self, validated_data):
        email = validated_data['email']
        request = self.context['request']

        try:
            with transaction.atomic():
                invite = (
                    AdminInvite.objects
                    .select_for_update()
                    .filter(email__iexact=email)
                    .first()
                )

                if invite is not None:
                    invite.email = email
                    invite.renew(
                        created_by=request.user,
                    )
                    return invite

                return AdminInvite.objects.create(
                    email=email,
                    created_by=request.user,
                )

        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    'email': (
                        'Não foi possível criar o convite. '
                        'Tente novamente.'
                    )
                }
            ) from exc


class AdminInviteRegistrationSerializer(
    serializers.ModelSerializer
):
    """Cadastro de administrador por meio de convite."""

    token = serializers.UUIDField(
        write_only=True,
    )

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = [
            'token',
            'name',
            'email',
            'password',
        ]

    def validate(self, attrs):
        email = User.objects.normalize_email(
            attrs['email'],
        ).strip().lower()

        try:
            invite = AdminInvite.objects.get(
                token=attrs['token'],
            )
        except AdminInvite.DoesNotExist as exc:
            raise serializers.ValidationError(
                {
                    'token': 'Convite inválido.',
                }
            ) from exc

        if not invite.is_valid():
            raise serializers.ValidationError(
                {
                    'token': (
                        'Este convite expirou ou já foi utilizado.'
                    )
                }
            )

        if invite.email.casefold() != email.casefold():
            raise serializers.ValidationError(
                {
                    'email': (
                        'O e-mail deve ser o mesmo para '
                        'o qual o convite foi enviado.'
                    )
                }
            )

        if User.objects.filter(
            email__iexact=email,
        ).exists():
            raise serializers.ValidationError(
                {
                    'email': (
                        'Já existe um usuário com este e-mail.'
                    )
                }
            )

        usuario_temporario = User(
            email=email,
            name=attrs.get('name', ''),
            is_staff=True,
        )

        try:
            password_validation.validate_password(
                attrs['password'],
                user=usuario_temporario,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {
                    'password': list(exc.messages),
                }
            ) from exc

        attrs['email'] = email

        return attrs

    def create(self, validated_data):
        token = validated_data.pop('token')
        password = validated_data.pop('password')
        email = validated_data['email']

        try:  # ruff: ignore[too-many-statements-in-try-clause]
            with transaction.atomic():
                try:
                    invite = (
                        AdminInvite.objects
                        .select_for_update()
                        .get(token=token)
                    )
                except AdminInvite.DoesNotExist as exc:
                    raise serializers.ValidationError(
                        {
                            'token': 'Convite inválido.',
                        }
                    ) from exc

                if not invite.is_valid():
                    raise serializers.ValidationError(
                        {
                            'token': (
                                'Este convite expirou ou '
                                'já foi utilizado.'
                            )
                        }
                    )

                if (
                    invite.email.casefold()
                    != email.casefold()
                ):
                    raise serializers.ValidationError(
                        {
                            'email': (
                                'O e-mail não corresponde '
                                'ao convite.'
                            )
                        }
                    )

                if User.objects.filter(
                    email__iexact=email,
                ).exists():
                    raise serializers.ValidationError(
                        {
                            'email': (
                                'Já existe um usuário '
                                'com este e-mail.'
                            )
                        }
                    )

                user = User.objects.create_user(
                    email=email,
                    name=validated_data.get(
                        'name',
                        '',
                    ),
                    password=password,
                    is_staff=True,
                    is_active=True,
                    email_verified=True,
                )

                invite.used = True
                invite.save(
                    update_fields=[
                        'used',
                    ]
                )

                return user

        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    'email': (
                        'Não foi possível concluir o cadastro '
                        'porque este e-mail já está em uso.'
                    )
                }
            ) from exc
