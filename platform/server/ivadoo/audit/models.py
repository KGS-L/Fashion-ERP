import uuid

from django.db import models


class AuditEvent(models.Model):
    class Result(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"
        DENIED = "denied", "Denied"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    company_id = models.UUIDField(null=True, blank=True, db_index=True)
    establishment_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_login = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=160, db_index=True)
    object_type = models.CharField(max_length=160, db_index=True)
    object_id = models.CharField(max_length=160, blank=True, db_index=True)
    object_label = models.CharField(max_length=255, blank=True)
    result = models.CharField(
        max_length=16,
        choices=Result.choices,
        default=Result.SUCCESS,
        db_index=True,
    )
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    request_id = models.CharField(max_length=128, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        indexes = [
            models.Index(
                fields=("organization", "action", "occurred_at"),
                name="audit_org_action_time_idx",
            ),
            models.Index(
                fields=("organization", "object_type", "object_id"),
                name="audit_org_object_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError("Audit events are immutable and cannot be updated.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError("Audit events are immutable and cannot be deleted.")

    def __str__(self) -> str:
        return f"{self.occurred_at} {self.action} {self.object_type}:{self.object_id}"
