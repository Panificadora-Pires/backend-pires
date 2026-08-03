from rest_framework import serializers

from core.models import AdminInvite, User


class AdminInviteCreateSerializer(serializers.ModelSerializer):
    """Serializer para Admins criarem convites."""
    class Meta:
        model = AdminInvite
        fields = ['email']

    def validate_email(self, value):
        # Verifica se já existe um usuário com este email
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Um usuário com este e-mail já existe.")
        return value

    def create(self, validated_data):
        # Associa o convite ao Admin que está criando
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class AdminInviteRegistrationSerializer(serializers.ModelSerializer):
    """Serializer para o convidado se registrar como Admin."""
    token = serializers.UUIDField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['token', 'name', 'email', 'password']

    def validate_token(self, value):
        try:
            invite = AdminInvite.objects.get(token=value)
        except AdminInvite.DoesNotExist:
            raise serializers.ValidationError("Convite inválido.")

        if not invite.is_valid():
            raise serializers.ValidationError("Este convite expirou ou já foi utilizado.")

        # Salva o convite no contexto para usar no create
        self.context['invite'] = invite
        return value

    def validate_email(self, value):
        # Garante que o email usado no registro é o mesmo do convite
        invite = self.context.get('invite')
        if invite and invite.email != value:
            raise serializers.ValidationError("O e-mail deve ser o mesmo para o qual o convite foi enviado.")
        return value

    def create(self, validated_data):
        validated_data.pop('token')
        password = validated_data.pop('password')
        invite = self.context['invite']

        # Cria o usuário como Admin (is_staff=True)
        user = User.objects.create_user(
            email=validated_data['email'],
            name=validated_data.get('name', ''),
            password=password,
            is_staff=True  # O convite garante que ele vira Admin
        )

        # Marca o convite como usado
        invite.used = True
        invite.save()

        return user
