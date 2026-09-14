from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('pedidos', '0003_pagamentos'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='mercadopago_order_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=80,
                verbose_name='ID da order no Mercado Pago',
            ),
        ),
        migrations.AddField(
            model_name='pedido',
            name='mercadopago_challenge_url',
            field=models.TextField(
                blank=True,
                verbose_name='URL do challenge 3DS do Mercado Pago',
            ),
        ),
    ]
