"""FAQ inicial do chatbot. Depois de aplicada, o conteúdo é editado pelo admin do Django."""

from django.db import migrations

FAQ_INICIAL = [
    {
        'chave': 'retirada',
        'pergunta': 'Como funciona a retirada?',
        'palavras_chave': 'retirada, retirar, retiro, buscar, pegar, qr code, qrcode, balcao, entrega',
        'resposta': (
            'Quando o pedido fica pronto, você recebe uma notificação no app. Vá ao balcão, abra Meus pedidos, '
            'toque em Ver QR Code e mostre a tela para a equipe. Ela lê o código e entrega o seu pedido.'
        ),
        'ordem': 10,
    },
    {
        'chave': 'pagamento',
        'pergunta': 'Quais são as formas de pagamento?',
        'palavras_chave': 'pag*, pix, cartao, credito, debito, dinheiro, troco, mercado pago',
        'resposta': (
            'Você pode pagar pelo app com Pix ou cartão (pelo Mercado Pago) ou escolher dinheiro na retirada. '
            'Pedidos pagos com Pix ou cartão só são confirmados depois que o pagamento é aprovado.'
        ),
        'ordem': 20,
    },
    {
        'chave': 'prazo_retirada',
        'pergunta': 'Quanto tempo tenho para retirar?',
        'palavras_chave': 'prazo, quanto tempo, tempo, demor*, atras*, expir*, esquec*',
        'resposta': (
            'Depois que o pedido fica pronto, você tem {minutos_retirada} minutos para retirar no balcão. '
            'Se não retirar nesse prazo, o pedido é cancelado automaticamente e, se foi pago pelo app, o valor '
            'é estornado. Pagamentos por Pix ou cartão precisam ser concluídos em até {minutos_pagamento} minutos; '
            'depois disso, o pedido é cancelado.'
        ),
        'ordem': 30,
    },
    {
        'chave': 'cancelamento',
        'pergunta': 'Como cancelo um pedido?',
        'palavras_chave': 'cancel*, desistir, desisti, estorn*, reembols*, devolu*',
        'resposta': (
            'O cancelamento é feito pela equipe da padaria. Abra a conversa do pedido (botão Falar com a padaria) '
            'e peça o cancelamento antes de retirar. Se você pagou com Pix ou cartão, o valor é estornado antes '
            'de o pedido ser cancelado.'
        ),
        'ordem': 40,
    },
    {
        'chave': 'horario',
        'pergunta': 'Qual o horário de atendimento?',
        'palavras_chave': 'horario, que horas, abre, abrem, fecha, fecham, aberto, aberta, expediente, funcionamento',
        'resposta': (
            'Pelo app, você pode fazer o pedido a qualquer hora, enquanto houver produtos disponíveis no cardápio. '
            'O horário do balcão ainda não está publicado aqui: confirme com a equipe da padaria.'
        ),
        'ordem': 50,
    },
]


def criar_faq(apps, schema_editor):
    PerguntaFrequente = apps.get_model('chatbot', 'PerguntaFrequente')
    for item in FAQ_INICIAL:
        PerguntaFrequente.objects.get_or_create(chave=item['chave'], defaults=item)


def remover_faq(apps, schema_editor):
    PerguntaFrequente = apps.get_model('chatbot', 'PerguntaFrequente')
    PerguntaFrequente.objects.filter(chave__in=[item['chave'] for item in FAQ_INICIAL]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('chatbot', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(criar_faq, remover_faq),
    ]
