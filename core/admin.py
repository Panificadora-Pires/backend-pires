"""Personalização do Django Admin."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from core import models


@admin.register(models.User)
class UserAdmin(BaseUserAdmin):
    """Configuração dos usuários no Django Admin."""

    ordering = ('id',)

    list_display = (
        'email',
        'name',
        'phone',
        'email_verified',
        'is_active',
        'is_staff',
        'possui_google',
    )

    list_filter = (
        'email_verified',
        'is_active',
        'is_staff',
        'is_superuser',
    )

    search_fields = (
        'email',
        'name',
        'phone',
        'google_sub',
        'groups__name',
    )

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'email',
                    'password',
                )
            },
        ),
        (
            _('Informações pessoais'),
            {
                'fields': (
                    'name',
                    'phone',
                    'google_sub',
                    'email_verified',
                )
            },
        ),
        (
            _('Permissões'),
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                )
            },
        ),
        (
            _('Datas importantes'),
            {
                'fields': (
                    'last_login',
                )
            },
        ),
        (
            _('Grupos'),
            {
                'fields': (
                    'groups',
                )
            },
        ),
        (
            _('Permissões individuais'),
            {
                'fields': (
                    'user_permissions',
                )
            },
        ),
    )

    readonly_fields = (
        'last_login',
        'google_sub',
        'email_verified',
    )

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'password1',
                    'password2',
                    'name',
                    'phone',
                    'is_active',
                    'is_staff',
                    'is_superuser',
                ),
            },
        ),
    )

    @admin.display(
        boolean=True,
        description='Conta Google',
    )
    def possui_google(self, obj):
        return bool(obj.google_sub)


@admin.register(models.AdminInvite)
class AdminInviteAdmin(admin.ModelAdmin):
    list_display = (
        'email',
        'created_by',
        'created_at',
        'expires_at',
        'used',
    )
    list_filter = ('used',)
    search_fields = ('email',)
    readonly_fields = (
        'token',
        'created_at',
        'expires_at',
    )


@admin.register(models.VerificationCode)
class VerificationCodeAdmin(admin.ModelAdmin):
    """Auditoria de desafios; o código em texto puro nunca é armazenado."""

    list_display = (
        'public_id',
        'user',
        'purpose',
        'attempts',
        'created_at',
        'expires_at',
        'used_at',
    )
    list_filter = (
        'purpose',
        'created_at',
        'used_at',
    )
    search_fields = (
        'public_id',
        'user__email',
    )
    readonly_fields = (
        'public_id',
        'user',
        'purpose',
        'code_hash',
        'attempts',
        'created_at',
        'expires_at',
        'used_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
