from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = AuditEvent
        fields = (
            "id",
            "occurred_at",
            "organization_id",
            "company_id",
            "establishment_id",
            "actor_id",
            "actor_login",
            "action",
            "object_type",
            "object_id",
            "object_label",
            "result",
            "before",
            "after",
            "request_id",
            "ip_address",
            "user_agent",
            "metadata",
        )
        read_only_fields = fields
