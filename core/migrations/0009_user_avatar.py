from django.core.validators import FileExtensionValidator
from django.db import migrations, models

import core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_user_verification'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar',
            field=models.ImageField(
                blank=True,
                help_text='Imagem JPG, PNG ou WebP com no máximo 3 MB.',
                null=True,
                upload_to='usuarios/avatars/%Y/%m/',
                validators=[
                    FileExtensionValidator(
                        allowed_extensions=[
                            'jpg',
                            'jpeg',
                            'png',
                            'webp',
                        ]
                    ),
                    core.validators.validar_tamanho_avatar,
                ],
                verbose_name='Foto de perfil',
            ),
        ),
    ]
