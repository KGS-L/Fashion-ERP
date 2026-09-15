from rest_framework import serializers

from ivadoo.catalog.models import Product, ProductVariant
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.organizations.models import Company, Establishment
from ivadoo.sales.models import Order

from .models import StockLocation, StockLot, StockMovement, StockPosition, StockReservation, Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all())
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment", queryset=Establishment.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = Warehouse
        fields = (
            "id", "organization_id", "company_id", "establishment_id", "code", "name",
            "is_active", "created_at", "updated_at",
        )
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get("establishment", getattr(self.instance, "establishment", None))
        if request and company.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"company_id": "Company is outside the local organization."})
        if establishment and establishment.company_id != company.id:
            raise serializers.ValidationError({"establishment_id": "Establishment must belong to the selected company."})
        return attrs


class StockLocationSerializer(serializers.ModelSerializer):
    warehouse_id = serializers.PrimaryKeyRelatedField(source="warehouse", queryset=Warehouse.objects.all())
    parent_id = serializers.PrimaryKeyRelatedField(source="parent", queryset=StockLocation.objects.all(), allow_null=True, required=False)

    class Meta:
        model = StockLocation
        fields = ("id", "warehouse_id", "parent_id", "code", "name", "kind", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if request and warehouse.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"warehouse_id": "Warehouse is outside the local organization."})
        if parent and parent.warehouse_id != warehouse.id:
            raise serializers.ValidationError({"parent_id": "Parent must belong to the selected warehouse."})
        return attrs


class StockPositionSerializer(serializers.ModelSerializer):
    warehouse_id = serializers.UUIDField(read_only=True)
    location_id = serializers.UUIDField(read_only=True)
    product_id = serializers.UUIDField(read_only=True)
    product_variant_id = serializers.UUIDField(read_only=True, allow_null=True)
    unit_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = StockPosition
        fields = (
            "id", "warehouse_id", "location_id", "product_id", "product_variant_id", "unit_id",
            "quantity_available", "quantity_reserved", "quantity_in_production",
            "quantity_damaged", "quantity_subcontractor", "updated_at",
        )
        read_only_fields = fields


class StockLotSerializer(serializers.ModelSerializer):
    warehouse_id = serializers.PrimaryKeyRelatedField(source="warehouse", queryset=Warehouse.objects.all())
    location_id = serializers.PrimaryKeyRelatedField(source="location", queryset=StockLocation.objects.all())
    product_id = serializers.PrimaryKeyRelatedField(source="product", queryset=Product.objects.all())
    product_variant_id = serializers.PrimaryKeyRelatedField(
        source="product_variant", queryset=ProductVariant.objects.all(), allow_null=True, required=False
    )
    unit_id = serializers.PrimaryKeyRelatedField(source="unit", queryset=UnitOfMeasure.objects.all())
    opening_quantity = serializers.DecimalField(max_digits=18, decimal_places=4, write_only=True, required=False)

    class Meta:
        model = StockLot
        fields = (
            "id", "warehouse_id", "location_id", "product_id", "product_variant_id", "unit_id",
            "code", "kind", "origin", "supplier_reference", "width", "initial_length",
            "remaining_length", "initial_quantity", "remaining_quantity", "opening_quantity",
            "reusable", "status", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "remaining_length", "initial_quantity", "remaining_quantity", "status", "created_at", "updated_at"
        )

    def validate(self, attrs):
        request = self.context.get("request")
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        location = attrs.get("location", getattr(self.instance, "location", None))
        product = attrs.get("product", getattr(self.instance, "product", None))
        product_variant = attrs.get("product_variant", getattr(self.instance, "product_variant", None))
        unit = attrs.get("unit", getattr(self.instance, "unit", None))
        if request and warehouse.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"warehouse_id": "Warehouse is outside the local organization."})
        if location.warehouse_id != warehouse.id:
            raise serializers.ValidationError({"location_id": "Location must belong to the selected warehouse."})
        if request and product.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"product_id": "Product is outside the local organization."})
        if product_variant and product_variant.product_id != product.id:
            raise serializers.ValidationError({"product_variant_id": "Variant must belong to the selected product."})
        if request and unit.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"unit_id": "Unit is outside the local organization."})
        if product.unit.category != unit.category:
            raise serializers.ValidationError({"unit_id": "Unit category must match the product unit category."})
        if self.instance and "opening_quantity" in attrs:
            raise serializers.ValidationError({"opening_quantity": "Opening quantity is only accepted when creating a lot."})
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    source_location_id = serializers.UUIDField(read_only=True, allow_null=True)
    destination_location_id = serializers.UUIDField(read_only=True, allow_null=True)
    product_id = serializers.UUIDField(read_only=True)
    product_variant_id = serializers.UUIDField(read_only=True, allow_null=True)
    unit_id = serializers.UUIDField(read_only=True)
    lot_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = StockMovement
        fields = (
            "id", "company_id", "source_location_id", "destination_location_id", "product_id",
            "product_variant_id", "unit_id", "lot_id", "movement_type", "quantity", "reason",
            "reference_type", "reference_id", "idempotency_key", "created_by_id", "created_at",
        )
        read_only_fields = fields


class StockMovementCreateSerializer(serializers.Serializer):
    movement_type = serializers.ChoiceField(choices=StockMovement.MovementType.choices)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    product_id = serializers.PrimaryKeyRelatedField(source="product", queryset=Product.objects.all())
    product_variant_id = serializers.PrimaryKeyRelatedField(source="product_variant", queryset=ProductVariant.objects.all(), allow_null=True, required=False)
    unit_id = serializers.PrimaryKeyRelatedField(source="unit", queryset=UnitOfMeasure.objects.all())
    source_location_id = serializers.PrimaryKeyRelatedField(source="source_location", queryset=StockLocation.objects.all(), allow_null=True, required=False)
    destination_location_id = serializers.PrimaryKeyRelatedField(source="destination_location", queryset=StockLocation.objects.all(), allow_null=True, required=False)
    lot_id = serializers.PrimaryKeyRelatedField(source="lot", queryset=StockLot.objects.all(), allow_null=True, required=False)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
    reference_type = serializers.CharField(max_length=80, required=False, allow_blank=True)
    reference_id = serializers.UUIDField(required=False, allow_null=True)
    idempotency_key = serializers.CharField(max_length=160, required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context["request"]
        organization_id = request.user.organization_id
        for name in ("product", "unit"):
            obj = attrs[name]
            if obj.organization_id != organization_id:
                raise serializers.ValidationError({f"{name}_id": f"{name.title()} is outside the local organization."})
        variant = attrs.get("product_variant")
        if variant and variant.product_id != attrs["product"].id:
            raise serializers.ValidationError({"product_variant_id": "Variant must belong to the selected product."})
        for name in ("source_location", "destination_location"):
            obj = attrs.get(name)
            if obj and obj.organization_id != organization_id:
                raise serializers.ValidationError({f"{name}_id": "Location is outside the local organization."})
        lot = attrs.get("lot")
        if lot and lot.organization_id != organization_id:
            raise serializers.ValidationError({"lot_id": "Lot is outside the local organization."})
        return attrs


class StockReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockReservation
        fields = (
            "id", "company_id", "warehouse_id", "location_id", "product_id", "product_variant_id",
            "unit_id", "lot_id", "order_id", "production_order_id", "quantity", "status",
            "idempotency_key", "created_by_id", "created_at", "updated_at", "released_at", "consumed_at",
        )
        read_only_fields = fields


class StockReservationCreateSerializer(serializers.Serializer):
    location_id = serializers.PrimaryKeyRelatedField(source="location", queryset=StockLocation.objects.all())
    product_id = serializers.PrimaryKeyRelatedField(source="product", queryset=Product.objects.all())
    product_variant_id = serializers.PrimaryKeyRelatedField(source="product_variant", queryset=ProductVariant.objects.all(), allow_null=True, required=False)
    unit_id = serializers.PrimaryKeyRelatedField(source="unit", queryset=UnitOfMeasure.objects.all())
    lot_id = serializers.PrimaryKeyRelatedField(source="lot", queryset=StockLot.objects.all(), allow_null=True, required=False)
    order_id = serializers.PrimaryKeyRelatedField(source="order", queryset=Order.objects.all(), allow_null=True, required=False)
    production_order_id = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4)
    idempotency_key = serializers.CharField(max_length=160, required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context["request"]
        organization_id = request.user.organization_id
        location = attrs["location"]
        product = attrs["product"]
        unit = attrs["unit"]
        if location.organization_id != organization_id:
            raise serializers.ValidationError({"location_id": "Location is outside the local organization."})
        if product.organization_id != organization_id:
            raise serializers.ValidationError({"product_id": "Product is outside the local organization."})
        if unit.organization_id != organization_id:
            raise serializers.ValidationError({"unit_id": "Unit is outside the local organization."})
        variant = attrs.get("product_variant")
        if variant and variant.product_id != product.id:
            raise serializers.ValidationError({"product_variant_id": "Variant must belong to the selected product."})
        lot = attrs.get("lot")
        if lot and (lot.organization_id != organization_id or lot.location_id != location.id or lot.product_id != product.id):
            raise serializers.ValidationError({"lot_id": "Lot must match the local organization, location and product."})
        order = attrs.get("order")
        if order and order.organization_id != organization_id:
            raise serializers.ValidationError({"order_id": "Order is outside the local organization."})
        return attrs
