from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from ivadoo.inventory.models import StockLocation, Warehouse

from .models import PurchaseOrder, PurchaseOrderLine, PurchaseReceipt, PurchaseReceiptLine


class PurchaseReceiptLineSerializer(serializers.ModelSerializer):
    purchase_order_line_id = serializers.PrimaryKeyRelatedField(
        source="purchase_order_line",
        queryset=PurchaseOrderLine.objects.all(),
    )
    location_id = serializers.PrimaryKeyRelatedField(
        source="location",
        queryset=StockLocation.objects.all(),
    )
    stock_movement_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = PurchaseReceiptLine
        fields = (
            "id",
            "purchase_order_line_id",
            "location_id",
            "received_quantity",
            "accepted_quantity",
            "rejected_quantity",
            "quality_status",
            "control_note",
            "stock_movement_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "accepted_quantity",
            "rejected_quantity",
            "quality_status",
            "control_note",
            "stock_movement_id",
            "created_at",
            "updated_at",
        )


class PurchaseReceiptSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    purchase_order_id = serializers.PrimaryKeyRelatedField(
        source="purchase_order",
        queryset=PurchaseOrder.objects.all(),
    )
    warehouse_id = serializers.PrimaryKeyRelatedField(
        source="warehouse",
        queryset=Warehouse.objects.all(),
    )
    created_by_id = serializers.UUIDField(read_only=True)
    controlled_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    posted_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    lines = PurchaseReceiptLineSerializer(many=True)

    class Meta:
        model = PurchaseReceipt
        fields = (
            "id",
            "organization_id",
            "company_id",
            "purchase_order_id",
            "warehouse_id",
            "number",
            "supplier_delivery_reference",
            "received_at",
            "status",
            "notes",
            "transition_reason",
            "created_by_id",
            "controlled_by_id",
            "posted_by_id",
            "controlled_at",
            "posted_at",
            "cancelled_at",
            "created_at",
            "updated_at",
            "lines",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "company_id",
            "status",
            "transition_reason",
            "created_by_id",
            "controlled_by_id",
            "posted_by_id",
            "controlled_at",
            "posted_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        request = self.context["request"]
        purchase_order = attrs["purchase_order"]
        warehouse = attrs["warehouse"]
        lines = attrs.get("lines", [])
        if purchase_order.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"purchase_order_id": "Purchase order is outside the local organization."}
            )
        if purchase_order.status != PurchaseOrder.Status.ORDERED:
            raise serializers.ValidationError(
                {"purchase_order_id": "Only ordered purchase orders may be received."}
            )
        if warehouse.organization_id != request.user.organization_id or warehouse.company_id != purchase_order.company_id:
            raise serializers.ValidationError(
                {"warehouse_id": "Warehouse must belong to the purchase order company."}
            )
        if purchase_order.warehouse_id and purchase_order.warehouse_id != warehouse.id:
            raise serializers.ValidationError(
                {"warehouse_id": "Warehouse must match the purchase order warehouse."}
            )
        if not lines:
            raise serializers.ValidationError({"lines": "At least one receipt line is required."})
        seen = set()
        for line in lines:
            po_line = line["purchase_order_line"]
            location = line["location"]
            if po_line.id in seen:
                raise serializers.ValidationError(
                    {"lines": "A purchase order line may only appear once per receipt."}
                )
            seen.add(po_line.id)
            if po_line.purchase_order_id != purchase_order.id:
                raise serializers.ValidationError(
                    {"lines": "Every receipt line must belong to the selected purchase order."}
                )
            if location.warehouse_id != warehouse.id:
                raise serializers.ValidationError(
                    {"lines": "Every destination location must belong to the receipt warehouse."}
                )
            if not location.is_active:
                raise serializers.ValidationError(
                    {"lines": "Destination locations must be active."}
                )
            outstanding = po_line.quantity - po_line.received_quantity
            if Decimal(line["received_quantity"]) > outstanding:
                raise serializers.ValidationError(
                    {"lines": "Received quantity exceeds the currently open purchase quantity."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        purchase_order = validated_data["purchase_order"]
        instance = PurchaseReceipt.objects.create(
            organization=purchase_order.organization,
            company=purchase_order.company,
            **validated_data,
        )
        for line in lines:
            PurchaseReceiptLine.objects.create(receipt=instance, **line)
        return instance


class ReceiptControlLineSerializer(serializers.Serializer):
    line_id = serializers.UUIDField()
    accepted_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    rejected_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_accepted_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Accepted quantity cannot be negative.")
        return value

    def validate_rejected_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Rejected quantity cannot be negative.")
        return value


class ReceiptActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("control", "post", "cancel"))
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
    lines = ReceiptControlLineSerializer(many=True, required=False)

    def validate(self, attrs):
        action = attrs["action"]
        lines = attrs.get("lines", [])
        if action == "control" and not lines:
            raise serializers.ValidationError(
                {"lines": "Control decisions are required for the control action."}
            )
        if action != "control" and lines:
            raise serializers.ValidationError(
                {"lines": "Control decisions are only accepted for the control action."}
            )
        return attrs


class SupplierPerformanceSerializer(serializers.Serializer):
    supplier_id = serializers.UUIDField()
    receipt_count = serializers.IntegerField()
    line_count = serializers.IntegerField()
    total_received = serializers.DecimalField(max_digits=28, decimal_places=4)
    total_accepted = serializers.DecimalField(max_digits=28, decimal_places=4)
    total_rejected = serializers.DecimalField(max_digits=28, decimal_places=4)
    acceptance_rate = serializers.DecimalField(max_digits=7, decimal_places=4)
    on_time_rate = serializers.DecimalField(max_digits=7, decimal_places=4, allow_null=True)
    average_lead_time_days = serializers.DecimalField(max_digits=12, decimal_places=4, allow_null=True)
