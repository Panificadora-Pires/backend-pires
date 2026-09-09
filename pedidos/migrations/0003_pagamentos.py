import uuid

from django.db import migrations, models


def preencher_checkout_ids(apps, schema_editor):
    Pedido = apps.get_model('pedidos', 'Pedido')
    for pedido in Pedido.objects.filter(checkout_id__isnull=True).iterator():
        pedido.checkout_id = uuid.uuid4()
        pedido.save(update_fields=['checkout_id'])


def normalizar_historico(apps, schema_editor):
    Pedido = apps.get_model('pedidos', 'Pedido')
    Pedido.objects.filter(status='retirado').update(status_pagamento='aprovado')


class Migration(migrations.Migration):
    dependencies = [
        ('pedidos', '0002_alter_pedido_status_atualizado_em'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='checkout_id',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='pedido',
            name='estoque_devolvido',
            field=models.BooleanField(default=False, verbose_name='estoque já devolvido após cancelamento'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='forma_pagamento',
            field=models.CharField(
                choices=[
                    ('dinheiro', 'Dinheiro na retirada'),
                    ('pix', 'Pix'),
                    ('cartao', 'Cartão'),
                ],
                default='dinheiro',
                max_length=20,
                verbose_name='forma de pagamento',
            ),
        ),
        migrations.AddField(
            model_name='pedido',
            name='mercadopago_payment_id',
            field=models.CharField(blank=True, db_index=True, max_length=80, verbose_name='ID do pagamento no Mercado Pago'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='mercadopago_status',
            field=models.CharField(blank=True, max_length=40, verbose_name='status bruto no Mercado Pago'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='mercadopago_status_detail',
            field=models.CharField(blank=True, max_length=120, verbose_name='detalhe do status no Mercado Pago'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='pagamento_expira_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='limite para concluir o pagamento online'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='pix_qr_code',
            field=models.TextField(blank=True, verbose_name='Pix copia e cola'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='pix_qr_code_base64',
            field=models.TextField(blank=True, verbose_name='QR Code Pix em base64'),
        ),
        migrations.AddField(
            model_name='pedido',
            name='status_pagamento',
            field=models.CharField(
                choices=[
                    ('pendente', 'Pendente'),
                    ('processando', 'Processando'),
                    ('aprovado', 'Aprovado'),
                    ('recusado', 'Recusado'),
                    ('cancelado', 'Cancelado'),
                    ('reembolsado', 'Reembolsado'),
                    ('erro', 'Erro'),
                ],
                default='pendente',
                max_length=20,
                verbose_name='status do pagamento',
            ),
        ),
        migrations.RunPython(preencher_checkout_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='pedido',
            name='checkout_id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
                verbose_name='identificador idempotente do checkout',
            ),
        ),
        migrations.RunPython(normalizar_historico, migrations.RunPython.noop),
    ]
