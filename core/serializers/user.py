import re

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers

from core.models import User


def normalize_brazilian_phone(value):
    """Normaliza telefone brasileiro para E.164 (+55...)."""

    digits = re.sub(r'\D', '', value or '')

    if digits.startswith('55') and len(digits) in {12, 13}:
        digits = digits[2:]

    if len(digits) not in {10, 11}:
        raise serializers.ValidationError(
            'Informe um telefone brasileiro válido com DDD.'
        )

    ddd = digits[:2]
    subscriber = digits[2:]

    if ddd.startswith('0') or subscriber.startswith('0'):
        raise serializers.ValidationError(
            'Informe um telefone brasileiro válido com DDD.'
        )

    return f'+55{digits}'


class UserSerializer(serializers.ModelSerializer):
    """Dados do usuário autenticado ou consultado pela administração."""

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
            'phone',
            'email_verified',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'groups',
        ]
        read_only_fields = fields


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Cadastro público de um usuário comum."""

    name = serializers.CharField(
        max_length=255,
        required=True,
        allow_blank=False,
        trim_whitespace=True,
    )

    phone = serializers.CharField(
        max_length=20,
        required=True,
        allow_blank=False,
    )

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
            'phone',
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

    def validate_phone(self, value):
        phone = normalize_brazilian_phone(value)

        if User.objects.filter(
            phone=phone,
        ).exists():
            raise serializers.ValidationError(
                'Já existe um usuário com este telefone.'
            )

        return phone

    def validate(self, attrs):
        usuario_temporario = User(
            email=attrs.get('email', ''),
            name=attrs.get('name', ''),
            phone=attrs.get('phone'),
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
        try:
            return User.objects.create_user(
                **validated_data,
                is_active=False,
                email_verified=False,
            )
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {
                    'detail': (
                        'Já existe uma conta com o e-mail '
                        'ou telefone informado.'
                    )
                }
            ) from exc
