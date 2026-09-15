from rest_framework import serializers

from ivadoo.manufacturing.models import ManufacturingOperation, ManufacturingOrder
from ivadoo.quality.models import QualityDefect

from .models import AlterationRequest, CustomerValidation, FittingSession, OrderLine


class FittingSessionSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    order_id = serializers.PrimaryKeyRelatedField(source="order", queryset=FittingSession._meta.get_field("order").remote_field.model.objects.all())
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = FittingSession
        fields = (
            "id", "organization_id", "company_id", "order_id", "scheduled_at", "performed_at",
            "status", "result", "requires_customer_validation", "notes", "created_by_id", "created_at", "updated_at",
        )
        read_only_fields = ("id", "organization_id", "company_id", "performed_at", "status", "result", "created_by_id", "created_at", "updated_at")

    def validate_order(self, order):
        request = self.context["request"]
        if order.organization_id != request.user.organization_id:
            raise serializers.ValidationError("Order is outside the local organization.")
        if order.status != order.Status.CONFIRMED:
            raise serializers.ValidationError("Fittings can be created only for confirmed orders.")
        return order


class FittingActionSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=(FittingSession.Result.FIT_OK, FittingSession.Result.ALTERATION_REQUIRED), required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class AlterationRequestSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    order_id = serializers.UUIDField(read_only=True)
    fitting_id = serializers.PrimaryKeyRelatedField(source="fitting", queryset=FittingSession.objects.all())
    order_line_id = serializers.PrimaryKeyRelatedField(source="order_line", queryset=OrderLine.objects.all(), required=False, allow_null=True)
    quality_defect_id = serializers.PrimaryKeyRelatedField(source="quality_defect", queryset=QualityDefect.objects.all(), required=False, allow_null=True)
    manufacturing_order_id = serializers.PrimaryKeyRelatedField(source="manufacturing_order", queryset=ManufacturingOrder.objects.all(), required=False, allow_null=True)
    manufacturing_operation_id = serializers.PrimaryKeyRelatedField(source="manufacturing_operation", queryset=ManufacturingOperation.objects.all(), required=False, allow_null=True)
    created_by_id = serializers.UUIDField(read_only=True)
    completed_by_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = AlterationRequest
        fields = (
            "id", "organization_id", "company_id", "order_id", "fitting_id", "order_line_id", "quality_defect_id",
            "manufacturing_order_id", "manufacturing_operation_id", "reason", "adjustment_notes", "priority", "status",
            "created_by_id", "completed_by_id", "started_at", "completed_at", "created_at", "updated_at",
        )
        read_only_fields = ("id", "organization_id", "company_id", "order_id", "status", "created_by_id", "completed_by_id", "started_at", "completed_at", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context["request"]
        fitting = attrs["fitting"]
        if fitting.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"fitting_id": "Fitting is outside the local organization."})
        order = fitting.order
        order_line = attrs.get("order_line")
        if order_line and order_line.order_id != order.id:
            raise serializers.ValidationError({"order_line_id": "Order line must belong to the fitting order."})
        defect = attrs.get("quality_defect")
        if defect and (defect.inspection.organization_id != request.user.organization_id or defect.inspection.company_id != order.company_id):
            raise serializers.ValidationError({"quality_defect_id": "Quality defect is outside the fitting scope."})
        mo = attrs.get("manufacturing_order")
        if mo and (mo.organization_id != request.user.organization_id or mo.company_id != order.company_id or mo.order_id != order.id):
            raise serializers.ValidationError({"manufacturing_order_id": "Manufacturing order must be linked to the fitting order."})
        operation = attrs.get("manufacturing_operation")
        if operation:
            if operation.organization_id != request.user.organization_id or operation.company_id != order.company_id or operation.manufacturing_order.order_id != order.id:
                raise serializers.ValidationError({"manufacturing_operation_id": "Manufacturing operation must belong to the fitting order."})
            if mo and operation.manufacturing_order_id != mo.id:
                raise serializers.ValidationError({"manufacturing_operation_id": "Manufacturing operation must belong to the selected manufacturing order."})
        return attrs


class AlterationActionSerializer(serializers.Serializer):
    reopen_operation = serializers.BooleanField(required=False, default=False)


class CustomerValidationSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    order_id = serializers.UUIDField(read_only=True)
    fitting_id = serializers.PrimaryKeyRelatedField(source="fitting", queryset=FittingSession.objects.all())
    recorded_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = CustomerValidation
        fields = (
            "id", "organization_id", "company_id", "order_id", "fitting_id", "decision", "customer_name", "notes",
            "evidence_reference", "recorded_by_id", "validated_at", "created_at",
        )
        read_only_fields = ("id", "organization_id", "company_id", "order_id", "recorded_by_id", "validated_at", "created_at")

    def validate_fitting(self, fitting):
        request = self.context["request"]
        if fitting.organization_id != request.user.organization_id:
            raise serializers.ValidationError("Fitting is outside the local organization.")
        if fitting.status != FittingSession.Status.COMPLETED or fitting.result != FittingSession.Result.FIT_OK:
            raise serializers.ValidationError("Customer validation requires a completed fitting with fit_ok result.")
        if CustomerValidation.objects.filter(fitting=fitting).exists():
            raise serializers.ValidationError("This fitting already has a customer validation record.")
        return fitting


class DeliveryReadinessSerializer(serializers.Serializer):
    deliverable = serializers.BooleanField()
    blockers = serializers.ListField(child=serializers.CharField())
