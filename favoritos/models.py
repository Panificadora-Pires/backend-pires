from django.conf import settings
from django.db import models


class Favorito(models.Model):
    """Produto salvo como favorito por um usuário."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favoritos',
        verbose_name='usuário',
    )
    produto = models.ForeignKey(
        'catalogo.Produto',
        on_delete=models.CASCADE,
        related_name='favoritado_por',
        verbose_name='produto',
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='criado em',
    )

    class Meta:
        verbose_name = 'Favorito'
        verbose_name_plural = 'Favoritos'
        ordering = ['-criado_em']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'produto'],
                name='favorito_usuario_produto_unico',
            ),
        ]

    def __str__(self):
        return f'{self.usuario} — {self.produto}'
