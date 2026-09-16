from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from ivadoo.catalog.models import FashionModel, FashionModelVariant
from ivadoo.customers.models import Customer
from ivadoo.internationalization.models import Currency
from ivadoo.measurements.models import MeasurementSet
from ivadoo.organizations.models import Company

from .models import (
    Order,
    OrderCommercialSnapshot,
    OrderLine,
    OrderLineVariantQuantity,
    Quotation,
    QuotationLine,
)


def _org(request):
    return request.user.organization_id if request else None


def _validate_positive_quantity(value):
    if value <= 0:
        raise serializers.ValidationError("Quantity must be greater than zero.")
    return value


def _validate_nonnegative_price(value):
    if value < 0:
        raise serializers.ValidationError("Unit price cannot be negative.")
    return value


def _validate_discount_rate(value):
    if value < Decimal("0") or value > Decimal("1"):
        raise serializers.ValidationError("Discount rate must be between 0 and 1 inclusive.")
    return value


def _validate_customization(value):
    if not isinstance(value, dict):
        raise serializers.ValidationError("Commercial customization must be a JSON object.")
    if len(value) > 50:
        raise serializers.ValidationError("Commercial customization cannot exceed 50 keys.")
    return value


class QuotationLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationLine
        fields = (
            "id",
            "fashion_model",
            "model_variant",
            "description",
            "quantity",
            "unit_price",
            "discount_rate",
        )
        read_only_fields = ("id",)

    def validate_quantity(self, value):
        return _validate_positive_quantity(value)

    def validate_unit_price(self, value):
        return _validate_nonnegative_price(value)

    def validate_discount_rate(self, value):
        return _validate_discount_rate(value)

    def validate(self, attrs):
        request = self.context.get("request")
        org_id = _org(request)
        model = attrs.get("fashion_model")
        variant = attrs.get("model_variant")
        if model and model.organization_id != org_id:
            raise serializers.ValidationError(
                {"fashion_model": "Fashion model is outside the organization."}
            )
        if variant and variant.fashion_model.organization_id != org_id:
            raise serializers.ValidationError(
                {"model_variant": "Model variant is outside the organization."}
            )
        if model and variant and variant.fashion_model_id != model.id:
            raise serializers.ValidationError(
                {"model_variant": "Variant does not belong to the selected fashion model."}
            )
        return attrs


class QuotationSerializer(serializers.ModelSerializer):
    lines = QuotationLineSerializer(many=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Quotation
        fields = (
            "id",
            "company",
            "customer",
            "currency",
            "number",
            "status",
            "valid_until",
            "notes",
            "lines",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        org_id = _org(request)
        company = attrs["company"]
        customer = attrs["customer"]
        if company.organization_id != org_id or customer.organization_id != org_id:
            raise serializers.ValidationError(
                "Company and customer must belong to the local organization."
            )
        if customer.company_id != company.id:
            raise serializers.ValidationError(
                {"customer": "Customer must belong to the selected company."}
            )
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop("lines")
        quotation = Quotation.objects.create(**validated_data)
        QuotationLine.objects.bulk_create(
            [QuotationLine(quotation=quotation, **line) for line in lines]
        )
        return quotation


class OrderLineVariantQuantitySerializer(serializers.ModelSerializer):
    size = serializers.CharField(source="model_variant.size", read_only=True)
    color = serializers.CharField(source="model_variant.color", read_only=True)
    variant_code = serializers.CharField(source="model_variant.code", read_only=True)

    class Meta:
        model = OrderLineVariantQuantity
        fields = (
            "id",
            "model_variant",
            "variant_code",
            "size",
            "color",
            "quantity",
            "commercial_customization",
        )
        read_only_fields = ("id", "variant_code", "size", "color")

    def validate_quantity(self, value):
        return _validate_positive_quantity(value)

    def validate_commercial_customization(self, value):
        return _validate_customization(value)

    def validate(self, attrs):
        request = self.context.get("request")
        variant = attrs.get("model_variant")
        if variant and request and variant.fashion_model.organization_id != _org(request):
            raise serializers.ValidationError(
                {"model_variant": "Model variant is outside the organization."}
            )
        return attrs


class OrderLineSerializer(serializers.ModelSerializer):
    variant_quantities = OrderLineVariantQuantitySerializer(many=True, required=False)

    class Meta:
        model = OrderLine
        fields = (
            "id",
            "fashion_model",
            "model_variant",
            "description",
            "quantity",
            "unit_price",
            "discount_rate",
            "fulfillment_mode",
            "commercial_customization",
            "variant_quantities",
            "measurement_set",
            "measurement_snapshot",
            "measurement_source_version",
        )
        read_only_fields = (
            "id",
            "measurement_snapshot",
            "measurement_source_version",
        )

    def validate_quantity(self, value):
        return _validate_positive_quantity(value)

    def validate_unit_price(self, value):
        return _validate_nonnegative_price(value)

    def validate_discount_rate(self, value):
        return _validate_discount_rate(value)

    def validate_commercial_customization(self, value):
        return _validate_customization(value)

    def validate(self, attrs):
        request = self.context.get("request")
        org_id = _org(request)
        model = attrs.get("fashion_model")
        variant = attrs.get("model_variant")
        measurement_set = attrs.get("measurement_set")
        allocations = attrs.get("variant_quantities", [])

        if model and model.organization_id != org_id:
            raise serializers.ValidationError(
                {"fashion_model": "Fashion model is outside the organization."}
            )
        if variant and variant.fashion_model.organization_id != org_id:
            raise serializers.ValidationError(
                {"model_variant": "Model variant is outside the organization."}
            )
        if model and variant and variant.fashion_model_id != model.id:
            raise serializers.ValidationError(
                {"model_variant": "Variant does not belong to the selected fashion model."}
            )
        if measurement_set and measurement_set.organization_id != org_id:
            raise serializers.ValidationError(
                {"measurement_set": "Measurement set is outside the organization."}
            )
        if allocations:
            if not model:
                raise serializers.ValidationError(
                    {"variant_quantities": "Variant quantities require a fashion model."}
                )
            if variant:
                raise serializers.ValidationError(
                    {"model_variant": "Use either model_variant or variant_quantities, not both."}
                )
            seen = set()
            for allocation in allocations:
                allocation_variant = allocation["model_variant"]
                if allocation_variant.fashion_model_id != model.id:
                    raise serializers.ValidationError(
                        {"variant_quantities": "Every variant must belong to the selected fashion model."}
                    )
                if allocation_variant.id in seen:
                    raise serializers.ValidationError(
                        {"variant_quantities": "A variant can appear only once per order line."}
                    )
                seen.add(allocation_variant.id)
        return attrs


class OrderCommercialSnapshotSerializer(serializers.ModelSerializer):
    confirmed_by_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = OrderCommercialSnapshot
        fields = (
            "id",
            "order_type",
            "subtotal",
            "discount_total",
            "total",
            "payload",
            "confirmed_by_id",
            "created_at",
        )
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True)
    status = serializers.CharField(read_only=True)
    confirmed_at = serializers.DateTimeField(read_only=True)
    cancelled_at = serializers.DateTimeField(read_only=True)
    created_by_id = serializers.UUIDField(read_only=True)
    commercial_snapshot = OrderCommercialSnapshotSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "company",
            "customer",
            "quotation",
            "number",
            "order_type",
            "status",
            "delivery_date",
            "event_date",
            "lines",
            "created_by_id",
            "commercial_snapshot",
            "confirmed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by_id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        org_id = _org(request)
        company = attrs["company"]
        customer = attrs["customer"]
        quotation = attrs.get("quotation")
        order_type = attrs.get("order_type", Order.OrderType.CUSTOM)
        delivery_date = attrs.get("delivery_date")
        event_date = attrs.get("event_date")

        if company.organization_id != org_id or customer.organization_id != org_id:
            raise serializers.ValidationError(
                "Company and customer must belong to the local organization."
            )
        if customer.company_id != company.id:
            raise serializers.ValidationError(
                {"customer": "Customer must belong to the selected company."}
            )
        if delivery_date and event_date and delivery_date > event_date:
            raise serializers.ValidationError(
                {"event_date": "Event date cannot be earlier than the delivery date."}
            )
        if quotation:
            if (
                quotation.organization_id != org_id
                or quotation.company_id != company.id
                or quotation.customer_id != customer.id
            ):
                raise serializers.ValidationError(
                    {
                        "quotation": (
                            "Quotation must belong to the same organization, company and customer."
                        )
                    }
                )
            if quotation.status != Quotation.Status.ACCEPTED:
                raise serializers.ValidationError(
                    {"quotation": "Only an accepted quotation can be converted to an order."}
                )

        for line in attrs["lines"]:
            measurement_set = line.get("measurement_set")
            allocations = line.get("variant_quantities", [])
            if measurement_set and (
                measurement_set.customer_id != customer.id
                or measurement_set.company_id != company.id
            ):
                raise serializers.ValidationError(
                    {
                        "lines": (
                            "Measurement set must belong to the order customer and company."
                        )
                    }
                )

            if order_type == Order.OrderType.CUSTOM:
                if allocations:
                    raise serializers.ValidationError(
                        {"lines": "Custom orders use a single model variant, not a variant quantity matrix."}
                    )
                continue

            if measurement_set:
                raise serializers.ValidationError(
                    {"lines": "Series and wholesale orders cannot use customer measurement sets."}
                )
            if not line.get("fashion_model"):
                raise serializers.ValidationError(
                    {"lines": "Series and wholesale lines require a fashion model."}
                )
            if not allocations:
                raise serializers.ValidationError(
                    {"lines": "Series and wholesale lines require variant quantities."}
                )
            allocated_quantity = sum(
                (Decimal(item["quantity"]) for item in allocations),
                Decimal("0"),
            )
            if allocated_quantity != Decimal(line["quantity"]):
                raise serializers.ValidationError(
                    {
                        "lines": (
                            "The sum of variant quantities must equal the order-line quantity."
                        )
                    }
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        order = Order.objects.create(**validated_data)
        for line_data in lines:
            variant_quantities = line_data.pop("variant_quantities", [])
            line = OrderLine.objects.create(order=order, **line_data)
            OrderLineVariantQuantity.objects.bulk_create(
                [
                    OrderLineVariantQuantity(order_line=line, **allocation)
                    for allocation in variant_quantities
                ]
            )
        return order
