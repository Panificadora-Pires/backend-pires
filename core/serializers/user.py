from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.models import User


class UserSerializer(serializers.ModelSerializer):
    """Dados públicos e administrativos de um usuário."""

    groups = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'name',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'groups',
        ]
        read_only_fields = fields


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Cadastro público de um usuário comum."""

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'name',
            'password',
        ]
        read_only_fields = [
            'id',
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

    def validate(self, attrs):
        usuario_temporario = User(
            email=attrs.get('email', ''),
            name=attrs.get('name', ''),
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

        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            **validated_data,
        )
