import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from fashionerp.internationalization.constants import SUPPORTED_LANGUAGES
from fashionerp.internationalization.validators import validate_language_code


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="users",
    )
    language_code = models.CharField(
        max_length=8,
        choices=SUPPORTED_LANGUAGES,
        default="fr",
        validators=[validate_language_code],
    )


class ApiSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_sessions",
    )
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    device_id = models.CharField(max_length=128, blank=True)
    device_label = models.CharField(max_length=128, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    idle_expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ("-created_at",)

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self, *, now=None) -> bool:
        current = now or timezone.now()
        return current >= self.expires_at or current >= self.idle_expires_at

    def revoke(self, *, reason: str = "user_requested") -> None:
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.revocation_reason = reason
            self.save(update_fields=["revoked_at", "revocation_reason"])
