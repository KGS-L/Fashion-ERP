from rest_framework import serializers

from ivadoo.internationalization.models import Currency
from ivadoo.organizations.models import Company, Establishment

from .models import (
    CommissionCalculation,
    CommissionRule,
    Employee,
    ProductivitySnapshot,
)


class ProductivitySnapshotSerializer(serializers.ModelSerializer):
    employee_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    establishment_id = serializers.UUIDField(read_only=True, allow_null=True)
    workshop_id = serializers.UUIDField(read_only=True, allow_null=True)
    generated_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ProductivitySnapshot
        fields = (
            "id",
            "employee_id",
            "company_id",
            "establishment_id",
            "workshop_id",
            "period_start",
            "period_end",
            "assigned_tasks",
            "completed_tasks",
            "task_completion_rate",
            "tracked_minutes",
            "linked_operation_count",
            "quantity_completion_rate",
            "formula_version",
            "source_fingerprint",
            "source_summary",
            "generated_by_id",
            "generated_at",
        )
        read_only_fields = fields


class ProductivityGenerateSerializer(serializers.Serializer):
    employee_id = serializers.PrimaryKeyRelatedField(
        source="employee", queryset=Employee.objects.all()
    )
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment",
        queryset=Establishment.objects.all(),
        allow_null=True,
        required=False,
    )
    workshop_id = serializers.PrimaryKeyRelatedField(
        source="workshop",
        queryset=Establishment.objects.filter(site_type__in=("workshop", "mixed")),
        allow_null=True,
        required=False,
    )
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    def validate(self, attrs):
        request = self.context.get("request")
        employee = attrs["employee"]
        company = attrs["company"]
        establishment = attrs.get("establishment")
        workshop = attrs.get("workshop")
        if request and employee.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"employee_id": "Employee is outside the local organization."}
            )
        if request and company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"company_id": "Company is outside the local organization."}
            )
        if employee.company_id != company.id:
            raise serializers.ValidationError(
                {"employee_id": "Employee must belong to the selected company."}
            )
        if establishment and establishment.company_id != company.id:
            raise serializers.ValidationError(
                {"establishment_id": "Establishment must belong to the selected company."}
            )
        if workshop and workshop.company_id != company.id:
            raise serializers.ValidationError(
                {"workshop_id": "Workshop must belong to the selected company."}
            )
        if attrs["period_end"] < attrs["period_start"]:
            raise serializers.ValidationError(
                {"period_end": "Period end cannot precede period start."}
            )
        return attrs


class CommissionRuleSerializer(serializers.ModelSerializer):
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
    workshop_id = serializers.PrimaryKeyRelatedField(
        source="workshop",
        queryset=Establishment.objects.filter(site_type__in=("workshop", "mixed")),
        allow_null=True,
        required=False,
    )
    employee_id = serializers.PrimaryKeyRelatedField(
        source="employee",
        queryset=Employee.objects.all(),
        allow_null=True,
        required=False,
    )
    currency_code = serializers.PrimaryKeyRelatedField(
        source="currency", queryset=Currency.objects.filter(is_active=True)
    )
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CommissionRule
        fields = (
            "id",
            "organization_id",
            "company_id",
            "establishment_id",
            "workshop_id",
            "employee_id",
            "code",
            "name",
            "basis",
            "rate",
            "currency_code",
            "active_from",
            "active_until",
            "is_active",
            "notes",
            "created_by_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
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
        workshop = attrs.get("workshop", getattr(self.instance, "workshop", None))
        employee = attrs.get("employee", getattr(self.instance, "employee", None))
        active_from = attrs.get("active_from", getattr(self.instance, "active_from", None))
        active_until = attrs.get(
            "active_until", getattr(self.instance, "active_until", None)
        )
        if request and company and company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"company_id": "Company is outside the local organization."}
            )
        if establishment and company and establishment.company_id != company.id:
            raise serializers.ValidationError(
                {"establishment_id": "Establishment must belong to the selected company."}
            )
        if workshop and company and workshop.company_id != company.id:
            raise serializers.ValidationError(
                {"workshop_id": "Workshop must belong to the selected company."}
            )
        if employee:
            if request and employee.organization_id != request.user.organization_id:
                raise serializers.ValidationError(
                    {"employee_id": "Employee is outside the local organization."}
                )
            if company and employee.company_id != company.id:
                raise serializers.ValidationError(
                    {"employee_id": "Employee must belong to the selected company."}
                )
        if active_from and active_until and active_until < active_from:
            raise serializers.ValidationError(
                {"active_until": "Active until cannot precede active from."}
            )
        return attrs


class CommissionCalculationSerializer(serializers.ModelSerializer):
    rule_id = serializers.UUIDField(read_only=True)
    employee_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    establishment_id = serializers.UUIDField(read_only=True, allow_null=True)
    workshop_id = serializers.UUIDField(read_only=True, allow_null=True)
    currency_code = serializers.CharField(source="currency_id", read_only=True)
    generated_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CommissionCalculation
        fields = (
            "id",
            "rule_id",
            "employee_id",
            "company_id",
            "establishment_id",
            "workshop_id",
            "period_start",
            "period_end",
            "basis_quantity",
            "rate_snapshot",
            "amount",
            "currency_code",
            "formula_version",
            "source_fingerprint",
            "rule_snapshot",
            "source_summary",
            "generated_by_id",
            "generated_at",
        )
        read_only_fields = fields


class CommissionCalculateSerializer(serializers.Serializer):
    rule_id = serializers.PrimaryKeyRelatedField(
        source="rule", queryset=CommissionRule.objects.select_related("currency", "company")
    )
    employee_id = serializers.PrimaryKeyRelatedField(
        source="employee", queryset=Employee.objects.all()
    )
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    def validate(self, attrs):
        request = self.context.get("request")
        rule = attrs["rule"]
        employee = attrs["employee"]
        if request and rule.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"rule_id": "Commission rule is outside the local organization."}
            )
        if request and employee.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"employee_id": "Employee is outside the local organization."}
            )
        if employee.company_id != rule.company_id:
            raise serializers.ValidationError(
                {"employee_id": "Employee must belong to the commission rule company."}
            )
        if rule.employee_id and rule.employee_id != employee.id:
            raise serializers.ValidationError(
                {"employee_id": "Commission rule is assigned to another employee."}
            )
        if attrs["period_end"] < attrs["period_start"]:
            raise serializers.ValidationError(
                {"period_end": "Period end cannot precede period start."}
            )
        return attrs
