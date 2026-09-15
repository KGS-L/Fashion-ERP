from rest_framework import serializers

from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.internationalization.models import Currency
from ivadoo.organizations.models import Company, Establishment

from .models import (
    CRMConversionEvent,
    CRMLead,
    CRMOpportunity,
    CRMPipelineStage,
    CRMSource,
)


def _validate_scope(*, request, company, establishment=None):
    if request and company and company.organization_id != request.user.organization_id:
        raise serializers.ValidationError(
            {"company_id": "Company is outside the local organization."}
        )
    if establishment and company and establishment.company_id != company.id:
        raise serializers.ValidationError(
            {"establishment_id": "Establishment must belong to the selected company."}
        )


class CRMSourceSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )

    class Meta:
        model = CRMSource
        fields = (
            "id",
            "organization_id",
            "company_id",
            "code",
            "name",
            "source_type",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")

    def validate(self, attrs):
        company = attrs.get("company", getattr(self.instance, "company", None))
        _validate_scope(
            request=self.context.get("request"),
            company=company,
        )
        if self.instance and company and company.id != self.instance.company_id:
            raise serializers.ValidationError(
                {"company_id": "Moving a CRM source to another company is not supported."}
            )
        return attrs


class CRMPipelineStageSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )

    class Meta:
        model = CRMPipelineStage
        fields = (
            "id",
            "organization_id",
            "company_id",
            "code",
            "name",
            "position",
            "stage_type",
            "probability",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")

    def validate(self, attrs):
        company = attrs.get("company", getattr(self.instance, "company", None))
        _validate_scope(
            request=self.context.get("request"),
            company=company,
        )
        if self.instance and company and company.id != self.instance.company_id:
            raise serializers.ValidationError(
                {"company_id": "Moving a pipeline stage to another company is not supported."}
            )
        return attrs


class CRMLeadSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment",
        queryset=Establishment.objects.all(),
        allow_null=True,
        required=False,
    )
    source_id = serializers.PrimaryKeyRelatedField(
        source="source",
        queryset=CRMSource.objects.all(),
        allow_null=True,
        required=False,
    )
    owner_id = serializers.PrimaryKeyRelatedField(
        source="owner",
        queryset=User.objects.all(),
        allow_null=True,
        required=False,
    )
    converted_customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    converted_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CRMLead
        fields = (
            "id",
            "organization_id",
            "company_id",
            "establishment_id",
            "source_id",
            "owner_id",
            "code",
            "prospect_type",
            "display_name",
            "first_name",
            "last_name",
            "legal_name",
            "email",
            "phone",
            "language_code",
            "status",
            "notes",
            "converted_customer_id",
            "converted_at",
            "converted_by_id",
            "created_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "converted_customer_id",
            "converted_at",
            "converted_by_id",
            "created_by_id",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        request = self.context.get("request")
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get(
            "establishment", getattr(self.instance, "establishment", None)
        )
        source = attrs.get("source", getattr(self.instance, "source", None))
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        status_value = attrs.get("status", getattr(self.instance, "status", CRMLead.Status.NEW))
        _validate_scope(
            request=request,
            company=company,
            establishment=establishment,
        )
        if source and company and source.company_id != company.id:
            raise serializers.ValidationError(
                {"source_id": "Source must belong to the selected company."}
            )
        if owner and request and owner.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"owner_id": "Owner is outside the local organization."}
            )
        if self.instance and company and company.id != self.instance.company_id:
            raise serializers.ValidationError(
                {"company_id": "Moving a lead to another company is not supported."}
            )
        if (
            status_value == CRMLead.Status.CONVERTED
            and (not self.instance or self.instance.status != CRMLead.Status.CONVERTED)
        ):
            raise serializers.ValidationError(
                {"status": "Use the lead conversion action to mark a lead as converted."}
            )
        return attrs


class CRMOpportunitySerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment",
        queryset=Establishment.objects.all(),
        allow_null=True,
        required=False,
    )
    lead_id = serializers.PrimaryKeyRelatedField(
        source="lead",
        queryset=CRMLead.objects.all(),
        allow_null=True,
        required=False,
    )
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer",
        queryset=Customer.objects.all(),
        allow_null=True,
        required=False,
    )
    source_id = serializers.PrimaryKeyRelatedField(
        source="source",
        queryset=CRMSource.objects.all(),
        allow_null=True,
        required=False,
    )
    stage_id = serializers.PrimaryKeyRelatedField(
        source="stage", queryset=CRMPipelineStage.objects.all()
    )
    owner_id = serializers.PrimaryKeyRelatedField(
        source="owner",
        queryset=User.objects.all(),
        allow_null=True,
        required=False,
    )
    currency_code = serializers.PrimaryKeyRelatedField(
        source="currency",
        queryset=Currency.objects.filter(is_active=True),
        allow_null=True,
        required=False,
    )
    converted_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CRMOpportunity
        fields = (
            "id",
            "organization_id",
            "company_id",
            "establishment_id",
            "lead_id",
            "customer_id",
            "source_id",
            "stage_id",
            "owner_id",
            "code",
            "title",
            "description",
            "prospect_type",
            "contact_name",
            "legal_name",
            "email",
            "phone",
            "language_code",
            "expected_revenue",
            "currency_code",
            "probability",
            "expected_close_date",
            "converted_at",
            "converted_by_id",
            "created_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "converted_at",
            "converted_by_id",
            "created_by_id",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        request = self.context.get("request")
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get(
            "establishment", getattr(self.instance, "establishment", None)
        )
        lead = attrs.get("lead", getattr(self.instance, "lead", None))
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        source = attrs.get("source", getattr(self.instance, "source", None))
        stage = attrs.get("stage", getattr(self.instance, "stage", None))
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        _validate_scope(
            request=request,
            company=company,
            establishment=establishment,
        )
        if lead and company and lead.company_id != company.id:
            raise serializers.ValidationError(
                {"lead_id": "Lead must belong to the selected company."}
            )
        if customer and company and customer.company_id != company.id:
            raise serializers.ValidationError(
                {"customer_id": "Customer must belong to the selected company."}
            )
        if source and company and source.company_id != company.id:
            raise serializers.ValidationError(
                {"source_id": "Source must belong to the selected company."}
            )
        if stage and company and stage.company_id != company.id:
            raise serializers.ValidationError(
                {"stage_id": "Stage must belong to the selected company."}
            )
        if owner and request and owner.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"owner_id": "Owner is outside the local organization."}
            )
        if self.instance and company and company.id != self.instance.company_id:
            raise serializers.ValidationError(
                {"company_id": "Moving an opportunity to another company is not supported."}
            )
        if self.instance and self.instance.converted_at and "customer" in attrs:
            if attrs["customer"] and attrs["customer"].id != self.instance.customer_id:
                raise serializers.ValidationError(
                    {"customer_id": "Converted opportunity customer is immutable."}
                )
        return attrs

    def create(self, validated_data):
        lead = validated_data.get("lead")
        company = validated_data["company"]
        if lead:
            validated_data.setdefault("establishment", lead.establishment)
            validated_data.setdefault("source", lead.source)
            validated_data.setdefault("owner", lead.owner)
        if "currency" not in validated_data:
            validated_data["currency"] = company.functional_currency
        if "probability" not in validated_data and validated_data.get("stage"):
            validated_data["probability"] = validated_data["stage"].probability
        return super().create(validated_data)


class CRMConversionEventSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    establishment_id = serializers.UUIDField(read_only=True, allow_null=True)
    lead_id = serializers.UUIDField(read_only=True, allow_null=True)
    opportunity_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_id = serializers.UUIDField(read_only=True)
    actor_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CRMConversionEvent
        fields = (
            "id",
            "organization_id",
            "company_id",
            "establishment_id",
            "source_kind",
            "lead_id",
            "opportunity_id",
            "customer_id",
            "created_customer",
            "source_snapshot",
            "actor_id",
            "occurred_at",
        )
        read_only_fields = fields


class CRMConvertSerializer(serializers.Serializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer",
        queryset=Customer.objects.all(),
        allow_null=True,
        required=False,
    )
    customer_code = serializers.CharField(max_length=64, required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context.get("request")
        customer = attrs.get("customer")
        if customer and request and customer.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"customer_id": "Customer is outside the local organization."}
            )
        return attrs
