from rest_framework import serializers

from .models import Company, Establishment, Organization


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


class CompanySerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Company
        fields = (
            "id",
            "organization_id",
            "name",
            "code",
            "legal_name",
            "registration_number",
            "tax_identifier",
            "country_code",
            "status",
            "created_at",
            "updated_at",
            "archived_at",
        )
        read_only_fields = fields


class EstablishmentSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(read_only=True)
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Establishment
        fields = (
            "id",
            "organization_id",
            "company_id",
            "name",
            "code",
            "site_type",
            "status",
            "address_line1",
            "address_line2",
            "city",
            "region",
            "country_code",
            "phone",
            "email",
            "created_at",
            "updated_at",
            "archived_at",
        )
        read_only_fields = fields
