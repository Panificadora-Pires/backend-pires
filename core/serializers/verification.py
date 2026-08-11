from rest_framework import serializers


class VerificationCodeSerializer(serializers.Serializer):
    """Confirma um código de seis dígitos."""

    request_id = serializers.UUIDField()
    code = serializers.RegexField(
        regex=r'^\d{6}$',
        error_messages={
            'invalid': 'O código deve possuir exatamente 6 dígitos.',
        },
    )


class ResendActivationSerializer(serializers.Serializer):
    """Solicita novo código de ativação."""

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetRequestSerializer(serializers.Serializer):
    """Solicita recuperação de senha."""

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(VerificationCodeSerializer):
    """Confirma o código e define a nova senha."""

    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )
