from decimal import Decimal

from rest_framework import serializers

from ivadoo.organizations.models import Company, Establishment

from .models import (
    ManufacturingOperation,
    ManufacturingOperationTransition,
    ManufacturingOrder,
    WorkCenter,
)


class WorkCenterSerializer(serializers.ModelSerializer):
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

    class Meta:
        model = WorkCenter
        fields = (
            "id",
            "organization_id",
            "company_id",
            "establishment_id",
            "code",
            "name",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context["request"]
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get(
            "establishment", getattr(self.instance, "establishment", None)
        )
        if company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"company_id": "Company is outside the local organization."}
            )
        if self.instance and company.id != self.instance.company_id:
            raise serializers.ValidationError(
                {"company_id": "Work center company cannot be changed after creation."}
            )
        if establishment and establishment.company_id != company.id:
            raise serializers.ValidationError(
                {"establishment_id": "Establishment must belong to the selected company."}
            )
        duplicate = WorkCenter.objects.filter(company=company, code=attrs.get("code", getattr(self.instance, "code", "")))
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {"code": "Work center code already exists in this company."}
            )
        return attrs


class ManufacturingOperationTransitionSerializer(serializers.ModelSerializer):
    actor_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ManufacturingOperationTransition
        fields = (
            "id",
            "from_status",
            "to_status",
            "action",
            "reason",
            "sequence_override",
            "processed_quantity",
            "actual_minutes",
            "actor_id",
            "occurred_at",
        )
        read_only_fields = fields


class ManufacturingOperationSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    manufacturing_order_id = serializers.UUIDField(read_only=True)
    work_center_id = serializers.PrimaryKeyRelatedField(
        source="work_center",
        queryset=WorkCenter.objects.all(),
        allow_null=True,
        required=False,
    )
    created_by_id = serializers.UUIDField(read_only=True)
    history = ManufacturingOperationTransitionSerializer(many=True, read_only=True)
    planned_quantity = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        required=False,
    )

    class Meta:
        model = ManufacturingOperation
        fields = (
            "id",
            "organization_id",
            "company_id",
            "manufacturing_order_id",
            "work_center_id",
            "operation_type",
            "name",
            "position",
            "status",
            "planned_minutes",
            "actual_minutes",
            "planned_quantity",
            "processed_quantity",
            "rework_count",
            "notes",
            "created_by_id",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "history",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "company_id",
            "manufacturing_order_id",
            "status",
            "actual_minutes",
            "processed_quantity",
            "rework_count",
            "created_by_id",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "history",
        )

    def validate(self, attrs):
        manufacturing_order = self.context["manufacturing_order"]
        if manufacturing_order.status not in (
            ManufacturingOrder.Status.DRAFT,
            ManufacturingOrder.Status.READY,
        ):
            raise serializers.ValidationError(
                "Operations can be planned only while the manufacturing order is draft or ready."
            )
        work_center = attrs.get("work_center")
        if work_center and (
            work_center.organization_id != manufacturing_order.organization_id
            or work_center.company_id != manufacturing_order.company_id
        ):
            raise serializers.ValidationError(
                {"work_center_id": "Work center is outside the manufacturing order company."}
            )
        planned_quantity = attrs.get(
            "planned_quantity", manufacturing_order.planned_quantity
        )
        if planned_quantity > manufacturing_order.planned_quantity:
            raise serializers.ValidationError(
                {"planned_quantity": "Operation quantity cannot exceed manufacturing order planned quantity."}
            )
        if ManufacturingOperation.objects.filter(
            manufacturing_order=manufacturing_order,
            position=attrs["position"],
        ).exists():
            raise serializers.ValidationError(
                {"position": "Another operation already uses this position in the manufacturing order."}
            )
        attrs["planned_quantity"] = planned_quantity
        return attrs

    def create(self, validated_data):
        manufacturing_order = self.context["manufacturing_order"]
        instance = ManufacturingOperation(
            organization=manufacturing_order.organization,
            company=manufacturing_order.company,
            manufacturing_order=manufacturing_order,
            created_by=self.context["request"].user,
            **validated_data,
        )
        instance.full_clean()
        instance.save()
        return instance


class ManufacturingOperationActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("start", "complete", "rework", "cancel"))
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
    processed_quantity = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        min_value=Decimal("0"),
        required=False,
    )
    actual_minutes = serializers.IntegerField(min_value=0, required=False)
    override_sequence = serializers.BooleanField(default=False, required=False)
