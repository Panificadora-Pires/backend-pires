"""Regras de negócio para códigos de verificação."""

import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import password_validation
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from core.models import User, VerificationCode


class VerificationError(Exception):
    """Erro genérico de verificação."""


class InvalidVerificationCode(VerificationError):
    """Código inválido, expirado, consumido ou bloqueado."""


@dataclass(frozen=True)
class IssuedChallenge:
    """Resultado da emissão de um desafio."""

    challenge: VerificationCode
    code: str | None
    retry_after_seconds: int

    @property
    def should_send_email(self):
        return self.code is not None


def _code_ttl():
    return timedelta(
        minutes=settings.VERIFICATION_CODE_TTL_MINUTES,
    )


def _max_attempts():
    return settings.VERIFICATION_MAX_ATTEMPTS


def _resend_cooldown():
    return settings.VERIFICATION_RESEND_COOLDOWN_SECONDS


def _generate_code():
    return f'{secrets.randbelow(1_000_000):06d}'


def _hash_code(public_id, code):
    """Gera HMAC do código usando SECRET_KEY como segredo do servidor."""

    return salted_hmac(
        'core.verification-code',
        f'{public_id}:{code}',
        secret=settings.SECRET_KEY,
        algorithm='sha256',
    ).hexdigest()


def _matches(challenge, code):
    expected = _hash_code(
        challenge.public_id,
        code,
    )

    return hmac.compare_digest(
        challenge.code_hash,
        expected,
    )


def _invalidate_open_challenges(user, purpose, now=None):
    now = now or timezone.now()

    VerificationCode.objects.filter(
        user=user,
        purpose=purpose,
        used_at__isnull=True,
    ).update(
        used_at=now,
    )



def invalidate_challenge(challenge):
    """Invalida um desafio emitido que não deve mais ser aceito."""

    now = timezone.now()
    VerificationCode.objects.filter(
        pk=challenge.pk,
        used_at__isnull=True,
    ).update(
        used_at=now,
    )

    challenge.used_at = now


def issue_challenge(user, purpose):
    """Invalida desafios anteriores e cria um novo código."""

    now = timezone.now()
    public_id = uuid.uuid4()
    code = _generate_code()

    with transaction.atomic():
        _invalidate_open_challenges(
            user=user,
            purpose=purpose,
            now=now,
        )

        challenge = VerificationCode.objects.create(
            public_id=public_id,
            user=user,
            purpose=purpose,
            code_hash=_hash_code(
                public_id,
                code,
            ),
            expires_at=now + _code_ttl(),
        )

    return IssuedChallenge(
        challenge=challenge,
        code=code,
        retry_after_seconds=_resend_cooldown(),
    )


def issue_or_reuse_challenge(user, purpose):
    """Respeita cooldown e emite novo código somente quando necessário."""

    now = timezone.now()
    cooldown = _resend_cooldown()

    with transaction.atomic():
        latest = (
            VerificationCode.objects
            .select_for_update()
            .filter(
                user=user,
                purpose=purpose,
                used_at__isnull=True,
            )
            .order_by('-created_at')
            .first()
        )

        if latest is not None:
            age = (now - latest.created_at).total_seconds()
            still_usable = (
                now < latest.expires_at
                and latest.attempts < _max_attempts()
            )

            if still_usable and age < cooldown:
                return IssuedChallenge(
                    challenge=latest,
                    code=None,
                    retry_after_seconds=max(
                        1,
                        int(cooldown - age),
                    ),
                )

        _invalidate_open_challenges(
            user=user,
            purpose=purpose,
            now=now,
        )

        public_id = uuid.uuid4()
        code = _generate_code()

        challenge = VerificationCode.objects.create(
            public_id=public_id,
            user=user,
            purpose=purpose,
            code_hash=_hash_code(
                public_id,
                code,
            ),
            expires_at=now + _code_ttl(),
        )

    return IssuedChallenge(
        challenge=challenge,
        code=code,
        retry_after_seconds=cooldown,
    )


def _validate_locked_challenge(public_id, purpose, code):
    """Valida o desafio bloqueado e persiste tentativas inválidas."""

    try:
        challenge = (
            VerificationCode.objects
            .select_for_update()
            .select_related('user')
            .get(
                public_id=public_id,
                purpose=purpose,
            )
        )
    except VerificationCode.DoesNotExist:
        return None, False

    now = timezone.now()

    if challenge.used_at is not None:
        return challenge, False

    if now >= challenge.expires_at:
        challenge.used_at = now
        challenge.save(
            update_fields=['used_at'],
        )
        return challenge, False

    if challenge.attempts >= _max_attempts():
        challenge.used_at = now
        challenge.save(
            update_fields=['used_at'],
        )
        return challenge, False

    if _matches(challenge, code):
        return challenge, True

    challenge.attempts += 1
    update_fields = ['attempts']

    if challenge.attempts >= _max_attempts():
        challenge.used_at = now
        update_fields.append('used_at')

    challenge.save(
        update_fields=update_fields,
    )

    return challenge, False


def activate_account(public_id, code):
    """Confirma o e-mail e ativa a conta pendente."""

    valid = False
    user = None

    with transaction.atomic():
        challenge, valid = _validate_locked_challenge(
            public_id=public_id,
            purpose=(
                VerificationCode.Purpose.ACCOUNT_ACTIVATION
            ),
            code=code,
        )

        if valid:
            user = User.objects.select_for_update().get(
                pk=challenge.user_id,
            )

            user.email_verified = True
            user.is_active = True
            user.save(
                update_fields=[
                    'email_verified',
                    'is_active',
                ]
            )

            now = timezone.now()
            challenge.used_at = now
            challenge.save(
                update_fields=['used_at'],
            )

            VerificationCode.objects.filter(
                user=user,
                purpose=(
                    VerificationCode.Purpose.ACCOUNT_ACTIVATION
                ),
                used_at__isnull=True,
            ).exclude(
                pk=challenge.pk,
            ).update(
                used_at=now,
            )

    if not valid:
        raise InvalidVerificationCode

    return user


def reset_password(public_id, code, new_password):
    """Valida o desafio e redefine a senha de forma atômica."""

    valid = False
    user = None

    with transaction.atomic():
        challenge, valid = _validate_locked_challenge(
            public_id=public_id,
            purpose=VerificationCode.Purpose.PASSWORD_RESET,
            code=code,
        )

        if valid:
            user = User.objects.select_for_update().get(
                pk=challenge.user_id,
            )

            if not user.is_active or not user.email_verified:
                valid = False
            else:
                password_validation.validate_password(
                    new_password,
                    user=user,
                )

                user.set_password(
                    new_password,
                )
                user.save(
                    update_fields=['password'],
                )

                now = timezone.now()
                challenge.used_at = now
                challenge.save(
                    update_fields=['used_at'],
                )

                VerificationCode.objects.filter(
                    user=user,
                    purpose=(
                        VerificationCode.Purpose.PASSWORD_RESET
                    ),
                    used_at__isnull=True,
                ).exclude(
                    pk=challenge.pk,
                ).update(
                    used_at=now,
                )

    if not valid:
        raise InvalidVerificationCode

    return user
