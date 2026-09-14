import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import ApiSession, User


def digest_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_api_session(
    *,
    user: User,
    device_id: str = "",
    device_label: str = "",
    user_agent: str = "",
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

    ApiSession.objects.filter(pk=session.pk, revoked_at__isnull=True).update(
        last_seen_at=now,
        idle_expires_at=next_idle_expiry,
    )
    session.last_seen_at = now
    session.idle_expires_at = next_idle_expiry
