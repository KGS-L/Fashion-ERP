from django.utils import timezone
from rest_framework import serializers

from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.organizations.models import Company, Establishment

from .models import CRMLead, CRMOpportunity
from .tracking_models import (
    CRMFollowUp,
    CRMInteraction,
    CRMSegment,
    CRMSegmentMembership,
)


def _uuid_field():
    return serializers.UUIDField(format="hex_verbose")


def _validate_scope(*, request, company, establishment=None):
    if request and company and company.organization_id != request.user.organization_id:
        raise serializers.ValidationError({"company_id": "Company is outside the local organization."})
    if establishment and company and establishment.company_id != company.id:
        raise serializers.ValidationError({"establishment_id": "Establishment must belong to the selected company."})


def _validate_target(*, company, lead=None, opportunity=None, customer=None):
    targets = [item for item in (lead, opportunity, customer) if item is not None]
    if len(targets) != 1:
        raise serializers.ValidationError(
            {"target": "Exactly one of lead_id, opportunity_id or customer_id is required."}
        )
    target = targets[0]
    if company and target.company_id != company.id:
        raise serializers.ValidationError({"target": "CRM target must belong to the selected company."})
    return target


class CRMSegmentSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company",
        queryset=Company.objects.all(),
        pk_field=_uuid_field(),
    )

    class Meta:
        model = CRMSegment
        fields = (
            "id", "organization_id", "company_id", "code", "name", "description",
            "is_active", "created_at", "updated_at",
        )
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")

    def validate(self, attrs):
        company = attrs.get("company", getattr(self.instance, "company", None))
        _validate_scope(request=self.context.get("request"), company=company)
        if self.instance and company and company.id != self.instance.company_id:
            raise serializers.ValidationError({"company_id": "Moving a segment to another company is not supported."})
        return attrs


class CRMSegmentMembershipSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    segment_id = serializers.PrimaryKeyRelatedField(
        source="segment",
        queryset=CRMSegment.objects.all(),
        pk_field=_uuid_field(),
    )
    lead_id = serializers.PrimaryKeyRelatedField(
        source="lead",
        queryset=CRMLead.objects.all(),
        pk_field=_uuid_field(),
        allow_null=True,
        required=False,
    )
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer",
        queryset=Customer.objects.all(),
        pk_field=_uuid_field(),
        allow_null=True,
        required=False,
    )
    added_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CRMSegmentMembership
        fields = (
            "id", "organization_id", "company_id", "segment_id", "lead_id",
            "customer_id", "added_by_id", "added_at",
        )
        read_only_fields = (
            "id", "organization_id", "company_id", "added_by_id", "added_at",
        )
        validators = ()

    def validate(self, attrs):
        request = self.context.get("request")
        segment = attrs.get("segment")
        lead = attrs.get("lead")
        customer = attrs.get("customer")
        if segment is None:
            raise serializers.ValidationError({"segment_id": "Segment is required."})
        _validate_scope(request=request, company=segment.company)
        _validate_target(company=segment.company, lead=lead, customer=customer)
        duplicate = CRMSegmentMembership.objects.filter(segment=segment)
        if lead is not None:
            duplicate = duplicate.filter(lead=lead)
        else:
            duplicate = duplicate.filter(customer=customer)
        if duplicate.exists():
            raise serializers.ValidationError(
                {"target": "This CRM target already belongs to the selected segment."}
            )
        return attrs


class CRMFollowUpSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all(), pk_field=_uuid_field()
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment", queryset=Establishment.objects.all(), pk_field=_uuid_field(),
        allow_null=True, required=False,
    )
    lead_id = serializers.PrimaryKeyRelatedField(
        source="lead", queryset=CRMLead.objects.all(), pk_field=_uuid_field(),
        allow_null=True, required=False,
    )
    opportunity_id = serializers.PrimaryKeyRelatedField(
        source="opportunity", queryset=CRMOpportunity.objects.all(), pk_field=_uuid_field(),
        allow_null=True, required=False,
    )
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer", queryset=Customer.objects.all(), pk_field=_uuid_field(),
        allow_null=True, required=False,
    )
    assignee_id = serializers.PrimaryKeyRelatedField(
        source="assignee", queryset=User.objects.all(), pk_field=_uuid_field(),
        allow_null=True, required=False,
    )
    completed_at = serializers.DateTimeField(read_only=True)
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CRMFollowUp
        fields = (
            "id", "organization_id", "company_id", "establishment_id", "lead_id",
            "opportunity_id", "customer_id", "assignee_id", "subject", "description",
            "due_at", "status", "priority", "completed_at", "created_by_id",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "organization_id", "completed_at", "created_by_id", "created_at", "updated_at",
        )

    def validate(self, attrs):
        request = self.context.get("request")
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get("establishment", getattr(self.instance, "establishment", None))
        lead = attrs.get("lead", getattr(self.instance, "lead", None))
        opportunity = attrs.get("opportunity", getattr(self.instance, "opportunity", None))
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        assignee = attrs.get("assignee", getattr(self.instance, "assignee", None))
        _validate_scope(request=request, company=company, establishment=establishment)
        _validate_target(company=company, lead=lead, opportunity=opportunity, customer=customer)
        if assignee and request and assignee.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"assignee_id": "Assignee is outside the local organization."})
        if self.instance and company and company.id != self.instance.company_id:
            raise serializers.ValidationError({"company_id": "Moving a follow-up to another company is not supported."})
        return attrs

    def create(self, validated_data):
        if validated_data.get("status") == CRMFollowUp.Status.COMPLETED:
            validated_data["completed_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        next_status = validated_data.get("status", instance.status)
        if next_status == CRMFollowUp.Status.COMPLETED and instance.status != CRMFollowUp.Status.COMPLETED:
            validated_data["completed_at"] = timezone.now()
        elif next_status != CRMFollowUp.Status.COMPLETED and instance.status == CRMFollowUp.Status.COMPLETED:
            validated_data["completed_at"] = None
        return super().update(instance, validated_data)


class CRMInteractionSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all(), pk_field=_uuid_field()
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment", queryset=Establishment.objects.all(), pk_field=_uuid_field(),
        allow_null=True, required=False,
    )
    lead_id = serializers.PrimaryKeyRelatedField(
        source="lead", queryset=CRMLead.objects.all(), pk_field=_uuid_field(),
        allow_null=True, required=False,
    )
    opportunity_id = serializers.PrimaryKeyRelatedField(
        source="opportunity", queryset=CRMOpportunity.objects.all(), pk_field=_uuid_field(),
        allow_null=True, required=False,
    )
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer", queryset=Customer.objects.all(), pk_field=_uuid_field(),
        allow_null=True, required=False,
    )
    actor_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CRMInteraction
        fields = (
            "id", "organization_id", "company_id", "establishment_id", "lead_id",
            "opportunity_id", "customer_id", "interaction_type", "channel", "direction",
            "subject", "summary", "occurred_at", "actor_id", "metadata", "created_at",
        )
        read_only_fields = ("id", "organization_id", "actor_id", "created_at")

    def validate(self, attrs):
        request = self.context.get("request")
        company = attrs.get("company")
        establishment = attrs.get("establishment")
        lead = attrs.get("lead")
        opportunity = attrs.get("opportunity")
        customer = attrs.get("customer")
        _validate_scope(request=request, company=company, establishment=establishment)
        _validate_target(company=company, lead=lead, opportunity=opportunity, customer=customer)
        return attrs
