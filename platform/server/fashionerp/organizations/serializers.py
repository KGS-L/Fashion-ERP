from rest_framework import serializers

from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "status",
            "created_at",
            "updated_at",
            "archived_at",
        )
        read_only_fields = fields
