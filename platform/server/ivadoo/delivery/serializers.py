from rest_framework import serializers

from ivadoo.inventory.models import StockLocation
from ivadoo.sales.models import Order, OrderLine

from .models import (
    Delivery,
    DeliveryLine,
    DeliveryPackage,
    DeliveryProof,
    DeliveryReturn,
    DeliveryReturnLine,
)
from .services import create_delivery, create_delivery_return


class DeliveryLineSerializer(serializers.ModelSerializer):
    order_line_id = serializers.PrimaryKeyRelatedField(source="order_line", queryset=OrderLine.objects.all())

    class Meta:
        model = DeliveryLine
        fields = ("id", "order_line_id", "quantity")
        read_only_fields = ("id",)


class DeliveryPackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryPackage
        fields = ("id", "code", "description", "is_sealed", "notes", "created_at")
        read_only_fields = ("id", "created_at")


class DeliveryProofSerializer(serializers.ModelSerializer):
    recorded_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = DeliveryProof
        fields = ("id", "proof_type", "recipient_name", "evidence_reference", "notes", "recorded_by_id", "recorded_at")
        read_only_fields = fields


class DeliverySerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    order_id = serializers.PrimaryKeyRelatedField(source="order", queryset=Order.objects.all())
    created_by_id = serializers.UUIDField(read_only=True)
    lines = DeliveryLineSerializer(many=True)
    packages = DeliveryPackageSerializer(many=True, required=False)
    proof = DeliveryProofSerializer(read_only=True)

    class Meta:
        model = Delivery
        fields = (
            "id", "organization_id", "company_id", "order_id", "number", "mode", "status",
            "courier_name", "courier_reference", "destination_notes", "failure_reason",
            "created_by_id", "prepared_at", "assigned_at", "shipped_at", "completed_at", "failed_at",
            "created_at", "updated_at", "lines", "packages", "proof",
        )
        read_only_fields = (
            "id", "organization_id", "company_id", "status", "failure_reason", "created_by_id",
            "prepared_at", "assigned_at", "shipped_at", "completed_at", "failed_at", "created_at", "updated_at", "proof",
        )

    def validate(self, attrs):
        request = self.context["request"]
        order = attrs["order"]
        if order.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"order_id": "Order is outside the local organization."})
        if order.status != Order.Status.CONFIRMED:
            raise serializers.ValidationError({"order_id": "Delivery requires a confirmed order."})
        lines = attrs.get("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "At least one delivery line is required."})
        for line in lines:
            if line["order_line"].order_id != order.id:
                raise serializers.ValidationError({"lines": "Every delivery line must belong to the selected order."})
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop("lines")
        packages = validated_data.pop("packages", [])
        return create_delivery(
            lines=lines,
            packages=packages,
            actor=self.context["request"].user,
            request=self.context["request"],
            **validated_data,
        )


class DeliveryProofInputSerializer(serializers.Serializer):
    proof_type = serializers.ChoiceField(choices=DeliveryProof.ProofType.choices)
    recipient_name = serializers.CharField(max_length=160)
    evidence_reference = serializers.CharField(max_length=500, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class DeliveryActionSerializer(serializers.Serializer):
    proof = DeliveryProofInputSerializer(required=False)
    failure_reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class DeliveryReturnLineSerializer(serializers.ModelSerializer):
    delivery_line_id = serializers.PrimaryKeyRelatedField(source="delivery_line", queryset=DeliveryLine.objects.all())
    destination_location_id = serializers.PrimaryKeyRelatedField(
        source="destination_location",
        queryset=StockLocation.objects.all(),
        required=False,
        allow_null=True,
    )
    stock_movements = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryReturnLine
        fields = (
            "id",
            "delivery_line_id",
            "quantity",
            "disposition",
            "destination_location_id",
            "stock_movements",
            "created_at",
        )
        read_only_fields = ("id", "stock_movements", "created_at")

    def get_stock_movements(self, obj):
        return [
            {
                "source_issue_movement_id": str(allocation.delivery_issue_movement_id),
                "return_movement_id": str(allocation.return_movement_id),
                "damage_movement_id": str(allocation.damage_movement_id) if allocation.damage_movement_id else None,
                "quantity": str(allocation.quantity),
            }
            for allocation in obj.stock_allocations.all()
        ]


class DeliveryReturnSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    delivery_id = serializers.PrimaryKeyRelatedField(source="delivery", queryset=Delivery.objects.all())
    created_by_id = serializers.UUIDField(read_only=True)
    lines = DeliveryReturnLineSerializer(many=True)

    class Meta:
        model = DeliveryReturn
        fields = (
            "id",
            "organization_id",
            "company_id",
            "delivery_id",
            "number",
            "reason",
            "resolution",
            "idempotency_key",
            "created_by_id",
            "created_at",
            "lines",
        )
        read_only_fields = ("id", "organization_id", "company_id", "created_by_id", "created_at")

    def validate(self, attrs):
        request = self.context["request"]
        delivery = attrs["delivery"]
        if delivery.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"delivery_id": "Delivery is outside the local organization."})
        lines = attrs.get("lines", [])
        if not lines:
            raise serializers.ValidationError({"lines": "At least one return line is required."})
        for line in lines:
            if line["delivery_line"].delivery_id != delivery.id:
                raise serializers.ValidationError({"lines": "Every return line must belong to the selected delivery."})
            destination = line.get("destination_location")
            if destination and destination.organization_id != request.user.organization_id:
                raise serializers.ValidationError({"lines": "Return destination is outside the local organization."})
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop("lines")
        return create_delivery_return(
            lines=lines,
            actor=self.context["request"].user,
            request=self.context["request"],
            **validated_data,
        )


class DeliveryBalanceLineSerializer(serializers.Serializer):
    order_line_id = serializers.UUIDField()
    ordered_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    allocated_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    delivered_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    returned_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    exchange_allowance_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    remaining_to_allocate = serializers.DecimalField(max_digits=18, decimal_places=4)
    customer_net_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)


class DeliveryBalanceSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    fully_allocated = serializers.BooleanField()
    operationally_complete = serializers.BooleanField()
    lines = DeliveryBalanceLineSerializer(many=True)
