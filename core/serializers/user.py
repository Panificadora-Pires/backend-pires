import re

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from core.models import User
from core.validators import MAX_AVATAR_SIZE_BYTES


ALLOWED_AVATAR_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
}


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
    """Dados públicos do usuário autenticado ou consultado pela administração."""

    groups = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field='name',
    )
    google_connected = serializers.SerializerMethodField()
    has_usable_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'name',
            'phone',
            'avatar',
            'email_verified',
            'google_connected',
            'has_usable_password',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'groups',
        ]
        read_only_fields = fields

    def get_google_connected(self, obj):
        return bool(obj.google_sub)

    def get_has_usable_password(self, obj):
        return obj.has_usable_password()


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Edição segura dos dados pessoais do próprio usuário."""

    name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
    )
    phone = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    avatar = serializers.ImageField(
        required=False,
        allow_null=True,
    )
    remove_avatar = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )

    class Meta:
        model = User
        fields = [
            'name',
            'phone',
            'avatar',
            'remove_avatar',
        ]

    def validate_phone(self, value):
        if value in {'', None}:
            return None

        phone = normalize_brazilian_phone(value)

        queryset = User.objects.filter(phone=phone)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                'Já existe um usuário com este telefone.'
            )

        return phone

    def validate_avatar(self, value):
        if value is None:
            return value

        if value.size > MAX_AVATAR_SIZE_BYTES:
            raise serializers.ValidationError(
                'A foto de perfil deve ter no máximo 3 MB.'
            )

        content_type = getattr(value, 'content_type', None)

        if content_type and content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
            raise serializers.ValidationError(
                'Envie uma imagem JPG, PNG ou WebP.'
            )

        return value

    def validate(self, attrs):
        if attrs.get('remove_avatar') and attrs.get('avatar') is not None:
            raise serializers.ValidationError(
                {
                    'avatar': (
                        'Escolha uma nova foto ou remova a atual, '
                        'não as duas opções ao mesmo tempo.'
                    )
                }
            )

        return attrs

    def update(self, instance, validated_data):
        remove_avatar = validated_data.pop('remove_avatar', False)
        avatar_enviado = 'avatar' in validated_data

        avatar_antigo_nome = None
        avatar_antigo_storage = None

        if instance.avatar:
            avatar_antigo_nome = instance.avatar.name
            avatar_antigo_storage = instance.avatar.storage

        if remove_avatar:
            validated_data['avatar'] = None
            avatar_enviado = True

        instance = super().update(instance, validated_data)

        if avatar_enviado and avatar_antigo_nome:
            avatar_novo_nome = (
                instance.avatar.name
                if instance.avatar
                else None
            )

            if avatar_novo_nome != avatar_antigo_nome:
                transaction.on_commit(
                    lambda: avatar_antigo_storage.delete(
                        avatar_antigo_nome
                    )
                )

        return instance


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
