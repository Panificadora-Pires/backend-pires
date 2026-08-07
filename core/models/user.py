"""
Modelo de usuário personalizado do sistema.
"""

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Manager responsável pela criação dos usuários."""

    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        """Cria e salva um usuário comum."""

        if not email:
            raise ValueError(
                'O usuário precisa possuir um endereço de e-mail.'
            )

        email = self.normalize_email(email).strip().lower()

        user = self.model(
            email=email,
            **extra_fields,
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)

        return user

    def create_superuser(
        self,
        email,
        password=None,
        **extra_fields,
    ):
        """Cria e salva um superusuário."""

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(
                'Um superusuário precisa possuir is_staff=True.'
            )

        if extra_fields.get('is_superuser') is not True:
            raise ValueError(
                'Um superusuário precisa possuir '
                'is_superuser=True.'
            )

        if not password:
            raise ValueError(
                'Um superusuário precisa possuir uma senha.'
            )

        return self.create_user(
            email=email,
            password=password,
            **extra_fields,
        )


class User(AbstractBaseUser, PermissionsMixin):
    """Usuário do sistema."""

    email = models.EmailField(
        max_length=255,
        unique=True,
        verbose_name=_('E-mail'),
        help_text=_('Endereço de e-mail do usuário.'),
    )

    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Nome'),
        help_text=_('Nome completo do usuário.'),
    )

    google_sub = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_('ID da conta Google'),
        help_text=_(
            'Identificador permanente da conta Google '
            'utilizado no login social.'
        ),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Usuário está ativo'),
        help_text=_(
            'Indica se este usuário pode acessar o sistema.'
        ),
    )

    is_staff = models.BooleanField(
        default=False,
        verbose_name=_('Usuário é da equipe'),
        help_text=_(
            'Indica se este usuário pode acessar '
            'o Django Admin.'
        ),
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
