from rest_framework import serializers

from ivadoo.internationalization.models import Currency

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
    functional_currency_id = serializers.PrimaryKeyRelatedField(
        source="functional_currency",
        queryset=Currency.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )

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
            "language_code",
            "functional_currency_id",
            "status",
            "created_at",
            "updated_at",
            "archived_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "created_at",
            "updated_at",
            "archived_at",
        )


class EstablishmentSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        source="company",
        queryset=Company.objects.all(),
    )
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
            "timezone",
            "created_at",
            "updated_at",
            "archived_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "created_at",
            "updated_at",
            "archived_at",
        )

    def validate_company_id(self, company):
        request = self.context.get("request")
        if request and company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                "Company is outside the local organization."
            )
        if self.instance and company.id != self.instance.company_id:
            raise serializers.ValidationError(
                "Moving an establishment to another company is not supported."
            )
        return company
