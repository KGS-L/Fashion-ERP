from rest_framework import serializers

from ivadoo.catalog.models import Product, ProductVariant
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.inventory.models import StockLocation, StockLot, StockMovement, Warehouse
from ivadoo.organizations.models import Company, Establishment

from .models import ApprovalRule, StockMovementApproval
from .services import create_stock_movement_approval


class ApprovalRuleSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all(), allow_null=True, required=False)
    establishment_id = serializers.PrimaryKeyRelatedField(source="establishment", queryset=Establishment.objects.all(), allow_null=True, required=False)
    warehouse_id = serializers.PrimaryKeyRelatedField(source="warehouse", queryset=Warehouse.objects.all(), allow_null=True, required=False)

    class Meta:
        model = ApprovalRule
        fields = ("id", "organization_id", "company_id", "establishment_id", "warehouse_id", "resource", "action", "threshold", "require_distinct_approver", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context["request"]
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get("establishment", getattr(self.instance, "establishment", None))
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        for obj, field in ((company, "company_id"), (establishment, "establishment_id"), (warehouse, "warehouse_id")):
            if obj and obj.organization_id != request.user.organization_id:
                raise serializers.ValidationError({field: "Scope is outside the local organization."})
        if establishment and (not company or establishment.company_id != company.id):
            raise serializers.ValidationError({"establishment_id": "Establishment must belong to the selected company."})
        if warehouse and (not company or warehouse.company_id != company.id):
            raise serializers.ValidationError({"warehouse_id": "Warehouse must belong to the selected company."})
        resource = attrs.get("resource", getattr(self.instance, "resource", None))
        action = attrs.get("action", getattr(self.instance, "action", None))
        if resource == ApprovalRule.Resource.PURCHASE_ORDER and action != "approve":
            raise serializers.ValidationError({"action": "Purchase-order approval rules support only the approve action in Phase 3."})
        if resource == ApprovalRule.Resource.STOCK_MOVEMENT and action not in StockMovement.MovementType.values:
            raise serializers.ValidationError({"action": "Stock approval action must be a supported stock movement type."})
        return attrs


class StockApprovalSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.UUIDField(read_only=True)
    establishment_id = serializers.UUIDField(read_only=True, allow_null=True)
    warehouse_id = serializers.UUIDField(read_only=True)
    requested_by_id = serializers.UUIDField(read_only=True)
    decided_by_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = StockMovementApproval
        fields = ("id", "organization_id", "company_id", "establishment_id", "warehouse_id", "movement_type", "quantity", "payload", "idempotency_key", "status", "requested_by_id", "decided_by_id", "decision_reason", "decided_at", "consumed_at", "consumed_movement_id", "created_at", "updated_at")
        read_only_fields = fields


class StockApprovalCreateSerializer(serializers.Serializer):
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
    idempotency_key = serializers.CharField(max_length=160)

    def validate(self, attrs):
        request = self.context["request"]
        organization_id = request.user.organization_id
        if attrs["product"].organization_id != organization_id or attrs["unit"].organization_id != organization_id:
            raise serializers.ValidationError("Product and unit must belong to the local organization.")
        location = attrs.get("source_location") or attrs.get("destination_location")
        if not location or location.organization_id != organization_id:
            raise serializers.ValidationError("A local stock location is required.")
        variant = attrs.get("product_variant")
        if variant and variant.product_id != attrs["product"].id:
            raise serializers.ValidationError({"product_variant_id": "Variant must belong to the selected product."})
        return attrs

    def create(self, validated_data):
        return create_stock_movement_approval(
            organization=self.context["request"].user.organization,
            actor=self.context["request"].user,
            data=validated_data,
            request=self.context["request"],
        )


class ApprovalDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=(("approve", "Approve"), ("reject", "Reject"), ("cancel", "Cancel")))
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
