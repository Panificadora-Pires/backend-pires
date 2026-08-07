"""
Personalização do Django Admin.
"""

from django.contrib import admin
from django.contrib.auth.admin import (
    UserAdmin as BaseUserAdmin,
)
from django.utils.translation import gettext_lazy as _

from core import models


@admin.register(models.User)
class UserAdmin(BaseUserAdmin):
    """Configuração dos usuários no Django Admin."""

    ordering = ('id',)

    list_display = (
        'email',
        'name',
        'is_active',
        'is_staff',
        'possui_google',
    )

    list_filter = (
        'is_active',
        'is_staff',
        'is_superuser',
    )

    search_fields = (
        'email',
        'name',
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
                    'google_sub',
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

    list_filter = (
        'used',
    )

    search_fields = (
        'email',
    )

    readonly_fields = (
        'token',
        'created_at',
        'expires_at',
    )
