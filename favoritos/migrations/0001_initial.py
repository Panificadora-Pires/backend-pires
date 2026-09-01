from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalogo', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Favorito',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'criado_em',
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name='criado em',
                    ),
                ),
                (
                    'produto',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='favoritado_por',
                        to='catalogo.produto',
                        verbose_name='produto',
                    ),
                ),
                (
                    'usuario',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='favoritos',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='usuário',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Favorito',
                'verbose_name_plural': 'Favoritos',
                'ordering': ['-criado_em'],
            },
        ),
        migrations.AddConstraint(
            model_name='favorito',
            constraint=models.UniqueConstraint(
                fields=('usuario', 'produto'),
                name='favorito_usuario_produto_unico',
            ),
        ),
    ]
