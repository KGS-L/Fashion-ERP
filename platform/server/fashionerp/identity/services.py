import hashlib
import hmac
import secrets
from datetime import timedelta

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiSession, RecoveryCode, TotpCredential, User


RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_GROUPS = 4
RECOVERY_CODE_GROUP_LENGTH = 4
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def digest_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _fernet() -> Fernet:
    try:
        return Fernet(settings.FASHIONERP_2FA_ENCRYPTION_KEY.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            "FASHIONERP_2FA_ENCRYPTION_KEY must be a valid Fernet key."
        ) from exc


def encrypt_totp_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_totp_secret(encrypted_secret: str) -> str:
    try:
        return _fernet().decrypt(
            encrypted_secret.encode("ascii")
        ).decode("ascii")
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt stored TOTP credential.") from exc


def recovery_code_digest(code: str) -> str:
    normalized = code.replace("-", "").replace(" ", "").upper()
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        normalized.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def generate_recovery_code() -> str:
    groups = []
    for _ in range(RECOVERY_CODE_GROUPS):
        groups.append(
            "".join(
                secrets.choice(RECOVERY_ALPHABET)
                for _ in range(RECOVERY_CODE_GROUP_LENGTH)
            )
        )
    return "-".join(groups)


def replace_recovery_codes(user: User) -> list[str]:
    codes: list[str] = []
    digests: set[str] = set()
    while len(codes) < RECOVERY_CODE_COUNT:
        code = generate_recovery_code()
        digest = recovery_code_digest(code)
        if digest in digests:
            continue
        codes.append(code)
        digests.add(digest)

    RecoveryCode.objects.filter(user=user).delete()
    RecoveryCode.objects.bulk_create(
        [
            RecoveryCode(user=user, code_digest=recovery_code_digest(code))
            for code in codes
        ]
    )
    return codes


def remaining_recovery_codes(user: User) -> int:
    return user.recovery_codes.filter(used_at__isnull=True).count()


def get_confirmed_totp_credential(user: User) -> TotpCredential | None:
    try:
        credential = user.totp_credential
    except TotpCredential.DoesNotExist:
        return None
    return credential if credential.is_confirmed else None


def two_factor_enabled(user: User) -> bool:
    return get_confirmed_totp_credential(user) is not None


def begin_totp_setup(user: User) -> tuple[TotpCredential, str, str]:
    if two_factor_enabled(user):
        raise ValueError("Two-factor authentication is already enabled.")

    secret = pyotp.random_base32()
    credential, _ = TotpCredential.objects.update_or_create(
        user=user,
        defaults={
            "encrypted_secret": encrypt_totp_secret(secret),
            "confirmed_at": None,
        },
    )
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.username,
        issuer_name=settings.FASHIONERP_TOTP_ISSUER,
    )
    return credential, secret, uri


def verify_totp_code(credential: TotpCredential, code: str) -> bool:
    secret = decrypt_totp_secret(credential.encrypted_secret)
    return bool(
        pyotp.TOTP(secret).verify(
            str(code).strip(),
            valid_window=1,
        )
    )


def verify_second_factor(
    user: User,
    code: str,
    *,
    allow_recovery: bool = True,
    consume_recovery: bool = True,
) -> str | None:
    credential = get_confirmed_totp_credential(user)
    if credential is None:
        return None

    normalized = str(code).strip()
    if normalized.isdigit() and len(normalized) == 6:
        if verify_totp_code(credential, normalized):
            return "totp"

    if not allow_recovery:
        return None

    digest = recovery_code_digest(normalized)
    with transaction.atomic():
        recovery = (
            RecoveryCode.objects.select_for_update()
            .filter(
                user=user,
                code_digest=digest,
                used_at__isnull=True,
            )
            .first()
        )
        if recovery is None:
            return None
        if consume_recovery:
            recovery.used_at = timezone.now()
            recovery.save(update_fields=["used_at"])
        return "recovery"


def confirm_totp_setup(user: User, code: str) -> list[str]:
    try:
        credential = user.totp_credential
    except TotpCredential.DoesNotExist as exc:
        raise ValueError("No pending TOTP setup exists.") from exc

    if credential.is_confirmed:
        raise ValueError("Two-factor authentication is already enabled.")

    if not verify_totp_code(credential, code):
        raise AuthenticationFailed("Invalid two-factor authentication code.")

    credential.confirmed_at = timezone.now()
    credential.save(update_fields=["confirmed_at", "updated_at"])
    return replace_recovery_codes(user)


def disable_two_factor(user: User) -> None:
    TotpCredential.objects.filter(user=user).delete()
    RecoveryCode.objects.filter(user=user).delete()


def revoke_user_sessions(
    user: User,
    *,
    reason: str,
    exclude_session_id=None,
) -> int:
    queryset = user.api_sessions.filter(revoked_at__isnull=True)
    if exclude_session_id is not None:
        queryset = queryset.exclude(pk=exclude_session_id)
    return queryset.update(
        revoked_at=timezone.now(),
        revocation_reason=reason,
    )


def create_api_session(
    *,
    user: User,
    device_id: str = "",
    device_label: str = "",
    user_agent: str = "",
    ip_address: str | None = None,
    two_factor_verified: bool = False,
) -> tuple[ApiSession, str]:
    now = timezone.now()
    raw_token = secrets.token_urlsafe(48)

    absolute_lifetime = timedelta(
        seconds=settings.FASHIONERP_SESSION_ABSOLUTE_TTL_SECONDS
    )
    idle_lifetime = timedelta(
        seconds=settings.FASHIONERP_SESSION_IDLE_TTL_SECONDS
    )

    expires_at = now + absolute_lifetime
    idle_expires_at = min(now + idle_lifetime, expires_at)

    session = ApiSession.objects.create(
        user=user,
        token_digest=digest_token(raw_token),
        device_id=device_id[:128],
        device_label=device_label[:128],
        user_agent=user_agent[:512],
        ip_address=ip_address,
        two_factor_verified=two_factor_verified,
        last_seen_at=now,
        expires_at=expires_at,
        idle_expires_at=idle_expires_at,
    )

    return session, raw_token


def touch_api_session(session: ApiSession) -> None:
    now = timezone.now()
    idle_lifetime = timedelta(
        seconds=settings.FASHIONERP_SESSION_IDLE_TTL_SECONDS
    )
    next_idle_expiry = min(now + idle_lifetime, session.expires_at)

    database_alias = session._state.db or "default"
    ApiSession.objects.using(database_alias).filter(
        pk=session.pk,
        revoked_at__isnull=True,
    ).update(
        last_seen_at=now,
        idle_expires_at=next_idle_expiry,
    )
    session.last_seen_at = now
    session.idle_expires_at = next_idle_expiry
