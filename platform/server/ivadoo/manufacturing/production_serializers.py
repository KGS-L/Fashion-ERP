from decimal import Decimal

from rest_framework import serializers

from ivadoo.inventory.models import StockLocation, StockLot, StockReservation

from .production_models import (
    ManufacturingMaterialConsumption,
    ManufacturingMaterialRemnant,
    ManufacturingOutputReceipt,
)


class MaterialConsumptionAllocationSerializer(serializers.Serializer):
    requirement_id = serializers.UUIDField()
    reservation_id = serializers.PrimaryKeyRelatedField(
        source="reservation",
        queryset=StockReservation.objects.all(),
        allow_null=True,
        required=False,
    )
    source_location_id = serializers.PrimaryKeyRelatedField(
        source="source_location",
        queryset=StockLocation.objects.all(),
        allow_null=True,
        required=False,
    )
    lot_id = serializers.PrimaryKeyRelatedField(
        source="lot",
        queryset=StockLot.objects.all(),
        allow_null=True,
        required=False,
    )
    quantity = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        min_value=Decimal("0.0001"),
    )
    disposition = serializers.ChoiceField(
        choices=ManufacturingMaterialConsumption.Disposition.choices,
        default=ManufacturingMaterialConsumption.Disposition.CONSUMED,
    )
    reason = serializers.CharField(max_length=255, allow_blank=True, required=False)
    idempotency_key = serializers.CharField(max_length=160)


class MaterialConsumptionRequestSerializer(serializers.Serializer):
    allocations = MaterialConsumptionAllocationSerializer(many=True, allow_empty=False)


class ManufacturingMaterialConsumptionSerializer(serializers.ModelSerializer):
    manufacturing_order_id = serializers.UUIDField(read_only=True)
    requirement_id = serializers.UUIDField(read_only=True)
    reservation_id = serializers.UUIDField(read_only=True, allow_null=True)
    source_location_id = serializers.UUIDField(read_only=True)
    product_id = serializers.UUIDField(read_only=True)
    product_variant_id = serializers.UUIDField(read_only=True, allow_null=True)
    unit_id = serializers.UUIDField(read_only=True)
    lot_id = serializers.UUIDField(read_only=True, allow_null=True)
    stock_movement_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ManufacturingMaterialConsumption
        fields = (
            "id",
            "manufacturing_order_id",
            "requirement_id",
            "reservation_id",
            "source_location_id",
            "product_id",
            "product_variant_id",
            "unit_id",
            "lot_id",
            "stock_movement_id",
            "source_type",
            "disposition",
            "quantity",
            "reason",
            "idempotency_key",
            "created_by_id",
            "created_at",
        )
        read_only_fields = fields


class ReusableRemnantRequestSerializer(serializers.Serializer):
    requirement_id = serializers.UUIDField()
    location_id = serializers.PrimaryKeyRelatedField(
        source="location", queryset=StockLocation.objects.all()
    )
    quantity = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        min_value=Decimal("0.0001"),
    )
    code = serializers.CharField(max_length=96)
    reason = serializers.CharField(max_length=255, allow_blank=True, required=False)
    idempotency_key = serializers.CharField(max_length=160)


class ManufacturingMaterialRemnantSerializer(serializers.ModelSerializer):
    manufacturing_order_id = serializers.UUIDField(read_only=True)
    requirement_id = serializers.UUIDField(read_only=True)
    location_id = serializers.UUIDField(read_only=True)
    product_id = serializers.UUIDField(read_only=True)
    product_variant_id = serializers.UUIDField(read_only=True, allow_null=True)
    unit_id = serializers.UUIDField(read_only=True)
    stock_lot_id = serializers.UUIDField(read_only=True)
    stock_movement_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ManufacturingMaterialRemnant
        fields = (
            "id",
            "manufacturing_order_id",
            "requirement_id",
            "location_id",
            "product_id",
            "product_variant_id",
            "unit_id",
            "stock_lot_id",
            "stock_movement_id",
            "quantity",
            "reason",
            "idempotency_key",
            "created_by_id",
            "created_at",
        )
        read_only_fields = fields


class MaterialVarianceRowSerializer(serializers.Serializer):
    requirement_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    product_variant_id = serializers.UUIDField(allow_null=True)
    unit_id = serializers.UUIDField()
    planned_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    gross_consumed_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    scrap_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    reusable_remnant_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    net_consumed_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    variance_quantity = serializers.DecimalField(max_digits=18, decimal_places=4)


class CompleteProductionRequestSerializer(serializers.Serializer):
    produced_quantity = serializers.DecimalField(
        max_digits=18,
        decimal_places=4,
        min_value=Decimal("0.0001"),
    )
    destination_location_id = serializers.PrimaryKeyRelatedField(
        source="destination_location", queryset=StockLocation.objects.all()
    )
    reason = serializers.CharField(max_length=255, allow_blank=True, required=False)


class ManufacturingOutputReceiptSerializer(serializers.ModelSerializer):
    manufacturing_order_id = serializers.UUIDField(read_only=True)
    destination_location_id = serializers.UUIDField(read_only=True)
    product_id = serializers.UUIDField(read_only=True)
    product_variant_id = serializers.UUIDField(read_only=True, allow_null=True)
    unit_id = serializers.UUIDField(read_only=True)
    stock_movement_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ManufacturingOutputReceipt
        fields = (
            "id",
            "manufacturing_order_id",
            "destination_location_id",
            "product_id",
            "product_variant_id",
            "unit_id",
            "stock_movement_id",
            "quantity",
            "created_by_id",
            "created_at",
        )
        read_only_fields = fields
