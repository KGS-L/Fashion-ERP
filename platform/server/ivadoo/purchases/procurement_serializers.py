from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from ivadoo.catalog.models import Product, ProductVariant
from ivadoo.internationalization.models import Currency, UnitOfMeasure
from ivadoo.inventory.models import Warehouse
from ivadoo.organizations.models import Company, Establishment
from ivadoo.sales.models import Order

from .models import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    RequestForQuotation,
    RFQSupplier,
    Supplier,
    SupplierQuotation,
    SupplierQuotationLine,
)


def _validate_item(*, product, variant, unit, organization_id, company_id):
    if product.organization_id != organization_id:
        raise serializers.ValidationError(
            {"product_id": "Product is outside the local organization."}
        )
    if product.company_id and product.company_id != company_id:
        raise serializers.ValidationError(
            {"product_id": "Company-specific product is outside the local company."}
        )
    if variant and variant.product_id != product.id:
        raise serializers.ValidationError(
            {"product_variant_id": "Variant must belong to the selected product."}
        )
    if unit.organization_id != organization_id:
        raise serializers.ValidationError(
            {"unit_id": "Unit is outside the local organization."}
        )
    if product.unit.category != unit.category:
        raise serializers.ValidationError(
            {"unit_id": "Unit category must match the product unit category."}
        )


class PurchaseRequestLineSerializer(serializers.ModelSerializer):
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
        model = PurchaseRequestLine
        fields = (
            "id",
            "product_id",
            "product_variant_id",
            "unit_id",
            "quantity",
            "need_reference_type",
            "need_reference_id",
            "notes",
        )
        read_only_fields = ("id",)


class PurchaseRequestSerializer(serializers.ModelSerializer):
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
    warehouse_id = serializers.PrimaryKeyRelatedField(
        source="warehouse",
        queryset=Warehouse.objects.all(),
        allow_null=True,
        required=False,
    )
    order_id = serializers.PrimaryKeyRelatedField(
        source="order", queryset=Order.objects.all(), allow_null=True, required=False
    )
    created_by_id = serializers.UUIDField(read_only=True)
    approved_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    lines = PurchaseRequestLineSerializer(many=True)

    class Meta:
        model = PurchaseRequest
        fields = (
            "id",
            "organization_id",
            "company_id",
            "establishment_id",
            "warehouse_id",
            "order_id",
            "number",
            "status",
            "needed_by",
            "notes",
            "transition_reason",
            "created_by_id",
            "approved_by_id",
            "submitted_at",
            "approved_at",
            "rejected_at",
            "cancelled_at",
            "created_at",
            "updated_at",
            "lines",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "status",
            "transition_reason",
            "created_by_id",
            "approved_by_id",
            "submitted_at",
            "approved_at",
            "rejected_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        request = self.context["request"]
        company = attrs.get("company", getattr(self.instance, "company", None))
        establishment = attrs.get(
            "establishment", getattr(self.instance, "establishment", None)
        )
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        order = attrs.get("order", getattr(self.instance, "order", None))
        if company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"company_id": "Company is outside the local organization."}
            )
        if establishment and establishment.company_id != company.id:
            raise serializers.ValidationError(
                {"establishment_id": "Establishment must belong to the selected company."}
            )
        if warehouse and warehouse.company_id != company.id:
            raise serializers.ValidationError(
                {"warehouse_id": "Warehouse must belong to the selected company."}
            )
        if order and (
            order.organization_id != request.user.organization_id
            or order.company_id != company.id
        ):
            raise serializers.ValidationError(
                {"order_id": "Order must belong to the selected company."}
            )
        for line in attrs.get("lines", []):
            _validate_item(
                product=line["product"],
                variant=line.get("product_variant"),
                unit=line["unit"],
                organization_id=request.user.organization_id,
                company_id=company.id,
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        instance = PurchaseRequest.objects.create(**validated_data)
        for line in lines:
            PurchaseRequestLine.objects.create(purchase_request=instance, **line)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        instance = super().update(instance, validated_data)
        if lines is not None:
            instance.lines.all().delete()
            for line in lines:
                PurchaseRequestLine.objects.create(purchase_request=instance, **line)
        return instance


class RequestForQuotationSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    purchase_request_id = serializers.PrimaryKeyRelatedField(
        source="purchase_request",
        queryset=PurchaseRequest.objects.all(),
        allow_null=True,
        required=False,
    )
    currency_code = serializers.PrimaryKeyRelatedField(
        source="currency", queryset=Currency.objects.all()
    )
    supplier_ids = serializers.PrimaryKeyRelatedField(
        source="suppliers_input",
        queryset=Supplier.objects.all(),
        many=True,
        write_only=True,
    )
    invited_supplier_ids = serializers.SerializerMethodField()
    created_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = RequestForQuotation
        fields = (
            "id",
            "organization_id",
            "company_id",
            "purchase_request_id",
            "number",
            "currency_code",
            "status",
            "due_date",
            "notes",
            "transition_reason",
            "supplier_ids",
            "invited_supplier_ids",
            "created_by_id",
            "sent_at",
            "closed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "status",
            "transition_reason",
            "invited_supplier_ids",
            "created_by_id",
            "sent_at",
            "closed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        )

    def get_invited_supplier_ids(self, obj) -> list[str]:
        return [
            str(value)
            for value in obj.supplier_links.order_by("supplier_id").values_list(
                "supplier_id", flat=True
            )
        ]

    def validate(self, attrs):
        request = self.context["request"]
        company = attrs.get("company", getattr(self.instance, "company", None))
        purchase_request = attrs.get(
            "purchase_request", getattr(self.instance, "purchase_request", None)
        )
        suppliers = attrs.get("suppliers_input", [])
        if company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"company_id": "Company is outside the local organization."}
            )
        if purchase_request and (
            purchase_request.organization_id != request.user.organization_id
            or purchase_request.company_id != company.id
        ):
            raise serializers.ValidationError(
                {"purchase_request_id": "Purchase request must belong to the selected company."}
            )
        if not self.instance and not suppliers:
            raise serializers.ValidationError(
                {"supplier_ids": "At least one supplier is required."}
            )
        for supplier in suppliers:
            if (
                supplier.organization_id != request.user.organization_id
                or supplier.company_id != company.id
            ):
                raise serializers.ValidationError(
                    {"supplier_ids": "Every supplier must belong to the selected company."}
                )
            if supplier.status != Supplier.Status.ACTIVE:
                raise serializers.ValidationError(
                    {"supplier_ids": "Only active suppliers may be invited."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        suppliers = validated_data.pop("suppliers_input")
        instance = RequestForQuotation.objects.create(**validated_data)
        RFQSupplier.objects.bulk_create(
            [RFQSupplier(rfq=instance, supplier=supplier) for supplier in suppliers]
        )
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        suppliers = validated_data.pop("suppliers_input", None)
        instance = super().update(instance, validated_data)
        if suppliers is not None:
            instance.supplier_links.all().delete()
            RFQSupplier.objects.bulk_create(
                [RFQSupplier(rfq=instance, supplier=supplier) for supplier in suppliers]
            )
        return instance


class SupplierQuotationLineSerializer(serializers.ModelSerializer):
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
        model = SupplierQuotationLine
        fields = (
            "id",
            "product_id",
            "product_variant_id",
            "unit_id",
            "quantity",
            "unit_price",
            "lead_time_days",
        )
        read_only_fields = ("id",)


class SupplierQuotationSerializer(serializers.ModelSerializer):
    rfq_id = serializers.UUIDField(read_only=True)
    supplier_id = serializers.PrimaryKeyRelatedField(
        source="supplier", queryset=Supplier.objects.all()
    )
    currency_code = serializers.CharField(source="rfq.currency_id", read_only=True)
    status = serializers.CharField(read_only=True)
    lines = SupplierQuotationLineSerializer(many=True)
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = SupplierQuotation
        fields = (
            "id",
            "rfq_id",
            "supplier_id",
            "currency_code",
            "quote_number",
            "status",
            "quoted_at",
            "valid_until",
            "notes",
            "lines",
            "total_amount",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "rfq_id",
            "currency_code",
            "status",
            "total_amount",
            "created_at",
            "updated_at",
        )

    def get_total_amount(self, obj) -> str:
        return str(
            sum(
                (line.quantity * line.unit_price for line in obj.lines.all()),
                Decimal("0"),
            )
        )

    def validate(self, attrs):
        request = self.context["request"]
        rfq = self.context["rfq"]
        supplier = attrs.get("supplier", getattr(self.instance, "supplier", None))
        if rfq.organization_id != request.user.organization_id:
            raise serializers.ValidationError("RFQ is outside the local organization.")
        if not rfq.supplier_links.filter(supplier=supplier).exists():
            raise serializers.ValidationError(
                {"supplier_id": "Supplier was not invited to this RFQ."}
            )
        for line in attrs.get("lines", []):
            _validate_item(
                product=line["product"],
                variant=line.get("product_variant"),
                unit=line["unit"],
                organization_id=request.user.organization_id,
                company_id=rfq.company_id,
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        instance = SupplierQuotation.objects.create(
            rfq=self.context["rfq"], **validated_data
        )
        for line in lines:
            SupplierQuotationLine.objects.create(quotation=instance, **line)
        return instance


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
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
    received_quantity = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True
    )

    class Meta:
        model = PurchaseOrderLine
        fields = (
            "id",
            "product_id",
            "product_variant_id",
            "unit_id",
            "quantity",
            "unit_price",
            "expected_date",
            "received_quantity",
        )
        read_only_fields = ("id", "received_quantity")


class PurchaseOrderSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        source="company", queryset=Company.objects.all()
    )
    warehouse_id = serializers.PrimaryKeyRelatedField(
        source="warehouse",
        queryset=Warehouse.objects.all(),
        allow_null=True,
        required=False,
    )
    supplier_id = serializers.PrimaryKeyRelatedField(
        source="supplier", queryset=Supplier.objects.all()
    )
    purchase_request_id = serializers.PrimaryKeyRelatedField(
        source="purchase_request",
        queryset=PurchaseRequest.objects.all(),
        allow_null=True,
        required=False,
    )
    rfq_id = serializers.PrimaryKeyRelatedField(
        source="rfq",
        queryset=RequestForQuotation.objects.all(),
        allow_null=True,
        required=False,
    )
    quotation_id = serializers.PrimaryKeyRelatedField(
        source="quotation",
        queryset=SupplierQuotation.objects.all(),
        allow_null=True,
        required=False,
    )
    currency_code = serializers.PrimaryKeyRelatedField(
        source="currency", queryset=Currency.objects.all()
    )
    created_by_id = serializers.UUIDField(read_only=True)
    approved_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    lines = PurchaseOrderLineSerializer(many=True)
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = (
            "id",
            "organization_id",
            "company_id",
            "warehouse_id",
            "supplier_id",
            "purchase_request_id",
            "rfq_id",
            "quotation_id",
            "currency_code",
            "number",
            "status",
            "notes",
            "transition_reason",
            "created_by_id",
            "approved_by_id",
            "submitted_at",
            "approved_at",
            "ordered_at",
            "cancelled_at",
            "lines",
            "total_amount",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization_id",
            "status",
            "transition_reason",
            "created_by_id",
            "approved_by_id",
            "submitted_at",
            "approved_at",
            "ordered_at",
            "cancelled_at",
            "total_amount",
            "created_at",
            "updated_at",
        )

    def get_total_amount(self, obj) -> str:
        return str(
            sum(
                (line.quantity * line.unit_price for line in obj.lines.all()),
                Decimal("0"),
            )
        )

    def validate(self, attrs):
        request = self.context["request"]
        company = attrs.get("company", getattr(self.instance, "company", None))
        supplier = attrs.get("supplier", getattr(self.instance, "supplier", None))
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        purchase_request = attrs.get(
            "purchase_request", getattr(self.instance, "purchase_request", None)
        )
        rfq = attrs.get("rfq", getattr(self.instance, "rfq", None))
        quotation = attrs.get("quotation", getattr(self.instance, "quotation", None))
        currency = attrs.get("currency", getattr(self.instance, "currency", None))
        if company.organization_id != request.user.organization_id:
            raise serializers.ValidationError(
                {"company_id": "Company is outside the local organization."}
            )
        if (
            supplier.organization_id != request.user.organization_id
            or supplier.company_id != company.id
        ):
            raise serializers.ValidationError(
                {"supplier_id": "Supplier must belong to the selected company."}
            )
        if supplier.status != Supplier.Status.ACTIVE:
            raise serializers.ValidationError({"supplier_id": "Supplier must be active."})
        if warehouse and warehouse.company_id != company.id:
            raise serializers.ValidationError(
                {"warehouse_id": "Warehouse must belong to the selected company."}
            )
        if purchase_request and (
            purchase_request.organization_id != request.user.organization_id
            or purchase_request.company_id != company.id
        ):
            raise serializers.ValidationError(
                {"purchase_request_id": "Purchase request must belong to the selected company."}
            )
        if rfq and (
            rfq.organization_id != request.user.organization_id
            or rfq.company_id != company.id
        ):
            raise serializers.ValidationError(
                {"rfq_id": "RFQ must belong to the selected company."}
            )
        if quotation:
            if not rfq or quotation.rfq_id != rfq.id:
                raise serializers.ValidationError(
                    {"quotation_id": "Quotation must belong to the selected RFQ."}
                )
            if quotation.supplier_id != supplier.id:
                raise serializers.ValidationError(
                    {"quotation_id": "Quotation supplier must match the purchase order supplier."}
                )
            if quotation.rfq.currency_id != currency.pk:
                raise serializers.ValidationError(
                    {"currency_code": "Purchase order currency must match the selected quotation."}
                )
        for line in attrs.get("lines", []):
            _validate_item(
                product=line["product"],
                variant=line.get("product_variant"),
                unit=line["unit"],
                organization_id=request.user.organization_id,
                company_id=company.id,
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        instance = PurchaseOrder.objects.create(**validated_data)
        for line in lines:
            PurchaseOrderLine.objects.create(purchase_order=instance, **line)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        instance = super().update(instance, validated_data)
        if lines is not None:
            instance.lines.all().delete()
            for line in lines:
                PurchaseOrderLine.objects.create(purchase_order=instance, **line)
        return instance


class TransitionSerializer(serializers.Serializer):
    action = serializers.CharField(max_length=32)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class QuoteComparisonItemSerializer(serializers.Serializer):
    quotation_id = serializers.UUIDField()
    supplier_id = serializers.UUIDField()
    supplier_name = serializers.CharField()
    currency_code = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=28, decimal_places=4)
    max_lead_time_days = serializers.IntegerField()
