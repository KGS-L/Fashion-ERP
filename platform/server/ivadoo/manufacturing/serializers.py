from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from ivadoo.catalog.models import FashionModel, FashionModelVariant, Product, ProductVariant
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.inventory.models import StockLocation, StockLot, Warehouse
from ivadoo.organizations.models import Company
from ivadoo.sales.models import Order, OrderLine

from .models import (
    BillOfMaterials,
    BillOfMaterialsLine,
    ManufacturingMaterialRequirement,
    ManufacturingOrder,
)
from .services import create_manufacturing_order


class BillOfMaterialsLineSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        source="product", queryset=Product.objects.all()
    )
    product_variant_id = serializers.PrimaryKeyRelatedField(
        source="product_variant",
        queryset=ProductVariant.objects.all(),
        allow_null=True,
        required=False,
    )
    unit_id = serializers.PrimaryKeyRelatedField(
        source="unit", queryset=UnitOfMeasure.objects.all()
    )

    class Meta:
        model = BillOfMaterialsLine
        fields = (
            "id",
            "product_id",
            "product_variant_id",
            "quantity",
            "unit_id",
            "waste_rate",
            "notes",
            "position",
        )
        read_only_fields = ("id",)


class BillOfMaterialsSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    fashion_model_id = serializers.PrimaryKeyRelatedField(
        source="fashion_model", queryset=FashionModel.objects.all()
    )
    model_variant_id = serializers.PrimaryKeyRelatedField(
        source="model_variant",
        queryset=FashionModelVariant.objects.all(),
        allow_null=True,
        required=False,
    )
    output_product_id = serializers.PrimaryKeyRelatedField(
        source="output_product",
        queryset=Product.objects.all(),
        allow_null=True,
        required=False,
    )
    output_product_variant_id = serializers.PrimaryKeyRelatedField(
        source="output_product_variant",
        queryset=ProductVariant.objects.all(),
        allow_null=True,
        required=False,
    )
    created_by_id = serializers.UUIDField(read_only=True)
    lines = BillOfMaterialsLineSerializer(many=True)

    class Meta:
        model = BillOfMaterials
        fields = (
            "id",
            "organization_id",
            "company_id",
            "fashion_model_id",
            "model_variant_id",
            "output_product_id",
            "output_product_variant_id",
            "code",
            "version",
            "status",
            "batch_quantity",
            "notes",
            "created_by_id",
            "activated_at",
            "archived_at",
            "created_at",
            "updated_at",
            "lines",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "status",
            "created_by_id",
            "activated_at",
            "archived_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        request = self.context["request"]
        if self.instance and self.instance.status != BillOfMaterials.Status.DRAFT:
            raise serializers.ValidationError(
                "Activated or archived BOM versions are immutable; create a new version instead."
            )
        company = attrs.get("company", getattr(self.instance, "company", None))
        fashion_model = attrs.get(
            "fashion_model", getattr(self.instance, "fashion_model", None)
        )
        model_variant = attrs.get(
            "model_variant", getattr(self.instance, "model_variant", None)
        )
        output_product = attrs.get(
            "output_product", getattr(self.instance, "output_product", None)
        )
        output_variant = attrs.get(
            "output_product_variant",
            getattr(self.instance, "output_product_variant", None),
        )
        if company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"company_id": "Company is outside the local organization."}
            )
        if fashion_model.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"fashion_model_id": "Fashion model is outside the local organization."}
            )
        if fashion_model.company_id and fashion_model.company_id != company.id:
            raise serializers.ValidationError(
                {"fashion_model_id": "Fashion model is outside the selected company."}
            )
        if model_variant and model_variant.fashion_model_id != fashion_model.id:
            raise serializers.ValidationError(
                {"model_variant_id": "Model variant must belong to the selected fashion model."}
            )
        if output_product:
            if output_product.organization_id != request.user.organization_id:
                raise serializers.ValidationError(
                    {"output_product_id": "Output product is outside the local organization."}
                )
            if output_product.company_id and output_product.company_id != company.id:
                raise serializers.ValidationError(
                    {"output_product_id": "Output product is outside the selected company."}
                )
            if output_product.product_type != Product.ProductType.FINISHED_GOOD:
                raise serializers.ValidationError(
                    {"output_product_id": "Output product must be a finished good."}
                )
        if output_variant and (
            not output_product or output_variant.product_id != output_product.id
        ):
            raise serializers.ValidationError(
                {"output_product_variant_id": "Output variant must belong to the output product."}
            )
        lines = attrs.get("lines", [])
        if not self.instance and not lines:
            raise serializers.ValidationError(
                {"lines": "At least one material line is required."}
            )
        for line in lines:
            product = line["product"]
            variant = line.get("product_variant")
            unit = line["unit"]
            if product.organization_id != request.user.organization_id:
                raise serializers.ValidationError(
                    {"lines": "Material product is outside the local organization."}
                )
            if product.company_id and product.company_id != company.id:
                raise serializers.ValidationError(
                    {"lines": "Company-specific material is outside the selected company."}
                )
            if variant and variant.product_id != product.id:
                raise serializers.ValidationError(
                    {"lines": "Material variant must belong to its product."}
                )
            if (
                unit.organization_id != request.user.organization_id
                or unit.category != product.unit.category
            ):
                raise serializers.ValidationError(
                    {
                        "lines": "Material unit must belong to the organization and match the product unit category."
                    }
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        instance = BillOfMaterials.objects.create(**validated_data)
        for line in lines:
            BillOfMaterialsLine.objects.create(bom=instance, **line)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        instance = super().update(instance, validated_data)
        if lines is not None:
            instance.lines.all().delete()
            for line in lines:
                BillOfMaterialsLine.objects.create(bom=instance, **line)
        return instance


class ManufacturingMaterialRequirementSerializer(serializers.ModelSerializer):
    source_bom_line_id = serializers.UUIDField(read_only=True)
    product_id = serializers.UUIDField(read_only=True)
    product_variant_id = serializers.UUIDField(read_only=True, allow_null=True)
    unit_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ManufacturingMaterialRequirement
        fields = (
            "id",
            "source_bom_line_id",
            "product_id",
            "product_variant_id",
            "unit_id",
            "quantity_per_unit",
            "waste_rate",
            "planned_quantity",
            "created_at",
        )
        read_only_fields = fields


class ManufacturingOrderSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    warehouse_id = serializers.PrimaryKeyRelatedField(
        source="warehouse", queryset=Warehouse.objects.all()
    )
    order_id = serializers.PrimaryKeyRelatedField(
        source="order", queryset=Order.objects.all(), allow_null=True, required=False
    )
    order_line_id = serializers.PrimaryKeyRelatedField(
        source="order_line",
        queryset=OrderLine.objects.all(),
        allow_null=True,
        required=False,
    )
    bom_id = serializers.PrimaryKeyRelatedField(
        source="bom", queryset=BillOfMaterials.objects.all()
    )
    created_by_id = serializers.UUIDField(read_only=True)
    material_requirements = ManufacturingMaterialRequirementSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = ManufacturingOrder
        fields = (
            "id",
            "organization_id",
            "company_id",
            "warehouse_id",
            "order_id",
            "order_line_id",
            "bom_id",
            "number",
            "status",
            "planned_quantity",
            "produced_quantity",
            "planned_start",
            "planned_end",
            "actual_start",
            "actual_end",
            "transition_reason",
            "created_by_id",
            "created_at",
            "updated_at",
            "material_requirements",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "status",
            "produced_quantity",
            "actual_start",
            "actual_end",
            "transition_reason",
            "created_by_id",
            "created_at",
            "updated_at",
            "material_requirements",
        )

    def validate(self, attrs):
        request = self.context["request"]
        company = attrs["company"]
        warehouse = attrs["warehouse"]
        bom = attrs["bom"]
        order = attrs.get("order")
        order_line = attrs.get("order_line")
        if company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"company_id": "Company is outside the local organization."}
            )
        if (
            warehouse.organization_id != request.user.organization_id
            or warehouse.company_id != company.id
        ):
            raise serializers.ValidationError(
                {"warehouse_id": "Warehouse is outside the selected company."}
            )
        if (
            bom.organization_id != request.user.organization_id
            or bom.company_id != company.id
        ):
            raise serializers.ValidationError(
                {"bom_id": "BOM is outside the selected company."}
            )
        if bom.status != BillOfMaterials.Status.ACTIVE:
            raise serializers.ValidationError(
                {"bom_id": "Manufacturing orders require an active BOM."}
            )
        if order:
            if (
                order.organization_id != request.user.organization_id
                or order.company_id != company.id
            ):
                raise serializers.ValidationError(
                    {"order_id": "Sales order is outside the selected company."}
                )
            if order.status != Order.Status.CONFIRMED:
                raise serializers.ValidationError(
                    {"order_id": "Only confirmed sales orders can drive manufacturing."}
                )
        if order_line:
            if not order or order_line.order_id != order.id:
                raise serializers.ValidationError(
                    {"order_line_id": "Order line must belong to the selected sales order."}
                )
            if (
                order_line.fashion_model_id
                and order_line.fashion_model_id != bom.fashion_model_id
            ):
                raise serializers.ValidationError(
                    {"bom_id": "BOM fashion model must match the order line."}
                )
            if (
                order_line.model_variant_id
                and bom.model_variant_id
                and order_line.model_variant_id != bom.model_variant_id
            ):
                raise serializers.ValidationError(
                    {"bom_id": "BOM variant must match the order line variant."}
                )
        return attrs

    def create(self, validated_data):
        return create_manufacturing_order(
            actor=self.context["request"].user,
            request=self.context["request"],
            organization=self.context["request"].user.organization,
            **validated_data,
        )


class BOMActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("activate", "archive"))


class ManufacturingOrderActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("ready", "start", "cancel"))
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class MaterialAllocationSerializer(serializers.Serializer):
    requirement_id = serializers.UUIDField()
    location_id = serializers.PrimaryKeyRelatedField(
        source="location", queryset=StockLocation.objects.all()
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
    idempotency_key = serializers.CharField(max_length=128)


class MaterialReservationRequestSerializer(serializers.Serializer):
    allocations = MaterialAllocationSerializer(many=True, allow_empty=False)


class MaterialReservationResultSerializer(serializers.Serializer):
    reservation_ids = serializers.ListField(child=serializers.UUIDField())
