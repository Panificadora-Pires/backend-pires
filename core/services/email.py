"""Envio de mensagens transacionais de autenticação."""

from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


def _send_email(*, subject, recipient, text_body, html_body):
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(
        html_body,
        'text/html',
    )

    return message.send(
        fail_silently=False,
    )


def send_account_activation_email(user, code):
    """Envia o código de ativação da conta."""

    nome = user.name or 'cliente'
    safe_name = escape(nome)
    safe_code = escape(code)

    text_body = (
        f'Olá, {nome}!\n\n'
        'Use o código abaixo para confirmar seu cadastro '
        'na Pires Panificadora:\n\n'
        f'{code}\n\n'
        f'Este código é válido por '
        f'{settings.VERIFICATION_CODE_TTL_MINUTES} minutos.\n\n'
        'Se você não criou uma conta, ignore esta mensagem.'
    )

    html_body = f"""
    <div style="font-family:Arial,sans-serif;color:#2A150B;line-height:1.5">
      <h2 style="color:#C8922E">Pires Panificadora</h2>
      <p>Olá, {safe_name}!</p>
      <p>Use o código abaixo para confirmar seu cadastro:</p>
      <p style="font-size:32px;font-weight:700;letter-spacing:6px">
        {safe_code}
      </p>
      <p>
        Este código é válido por
        {settings.VERIFICATION_CODE_TTL_MINUTES} minutos.
      </p>
      <p>Se você não criou uma conta, ignore esta mensagem.</p>
    </div>
    """

    return _send_email(
        subject='Confirme seu cadastro - Pires Panificadora',
        recipient=user.email,
        text_body=text_body,
        html_body=html_body,
    )


def send_password_reset_email(user, code):
    """Envia o código de redefinição de senha."""

    nome = user.name or 'cliente'
    safe_name = escape(nome)
    safe_code = escape(code)

    text_body = (
        f'Olá, {nome}!\n\n'
        'Recebemos uma solicitação para redefinir sua senha.\n\n'
        f'Seu código é: {code}\n\n'
        f'Este código é válido por '
        f'{settings.VERIFICATION_CODE_TTL_MINUTES} minutos.\n\n'
        'Se você não solicitou a alteração, ignore esta mensagem.'
    )

    html_body = f"""
    <div style="font-family:Arial,sans-serif;color:#2A150B;line-height:1.5">
      <h2 style="color:#C8922E">Pires Panificadora</h2>
      <p>Olá, {safe_name}!</p>
      <p>Recebemos uma solicitação para redefinir sua senha.</p>
      <p style="font-size:32px;font-weight:700;letter-spacing:6px">
        {safe_code}
      </p>
      <p>
        Este código é válido por
        {settings.VERIFICATION_CODE_TTL_MINUTES} minutos.
      </p>
      <p>Se você não solicitou a alteração, ignore esta mensagem.</p>
    </div>
    """

    return _send_email(
        subject='Redefinição de senha - Pires Panificadora',
        recipient=user.email,
        text_body=text_body,
        html_body=html_body,
    )
