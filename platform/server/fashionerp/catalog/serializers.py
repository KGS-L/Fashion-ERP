from rest_framework import serializers

from fashionerp.internationalization.models import UnitOfMeasure
from fashionerp.organizations.models import Company

from .models import Product, ProductAttribute, ProductAttributeValue, ProductVariant


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttributeValue
        fields = ("id", "code", "value", "position", "metadata")
        read_only_fields = ("id",)


class ProductAttributeSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    values = ProductAttributeValueSerializer(many=True, required=False)

    class Meta:
        model = ProductAttribute
        fields = ("id", "organization_id", "code", "name", "is_active", "values")
        read_only_fields = ("id", "organization_id")

    def create(self, validated_data):
        values = validated_data.pop("values", [])
        attribute = ProductAttribute.objects.create(**validated_data)
        ProductAttributeValue.objects.bulk_create(
            [ProductAttributeValue(attribute=attribute, **item) for item in values]
        )
        return attribute


class ProductVariantSerializer(serializers.ModelSerializer):
    attribute_value_ids = serializers.PrimaryKeyRelatedField(
        source="attribute_values", queryset=ProductAttributeValue.objects.all(),
        many=True, required=False,
    )

    class Meta:
        model = ProductVariant
        fields = ("id", "sku", "barcode", "name", "metadata", "is_active", "attribute_value_ids", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_attribute_values(self, values):
        product = self.context.get("product")
        if product and any(v.attribute.organization_id != product.organization_id for v in values):
            raise serializers.ValidationError("Attribute value is outside the product organization.")
        attributes = [v.attribute_id for v in values]
        if len(attributes) != len(set(attributes)):
            raise serializers.ValidationError("A variant can only select one value per attribute.")
        return values


class ProductSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all(), allow_null=True, required=False)
    unit_id = serializers.PrimaryKeyRelatedField(source="unit", queryset=UnitOfMeasure.objects.all())
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ("id", "organization_id", "company_id", "code", "name", "description", "product_type", "unit_id", "fashion_metadata", "is_active", "variants", "created_at", "updated_at")
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        company = attrs.get("company", getattr(self.instance, "company", None))
        unit = attrs.get("unit", getattr(self.instance, "unit", None))
        if request and company and company.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"company_id": "Company is outside the local organization."})
        if request and unit and unit.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"unit_id": "Unit is outside the local organization."})
        return attrs
