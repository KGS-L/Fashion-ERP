from rest_framework import serializers

from fashionerp.internationalization.models import UnitOfMeasure
from fashionerp.organizations.models import Company

from .models import (
    Collection, FashionModel, FashionModelMaterialRequirement, FashionModelVariant, Product, ProductAttribute,
    ProductAttributeValue, ProductVariant, Season,
)


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


class SeasonSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = Season
        fields = ("id", "organization_id", "code", "name", "year", "start_date", "end_date", "is_active")
        read_only_fields = ("id", "organization_id")

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot precede start date."})
        return attrs


class CollectionSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all(), allow_null=True, required=False)
    season_id = serializers.PrimaryKeyRelatedField(source="season", queryset=Season.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Collection
        fields = ("id", "organization_id", "company_id", "season_id", "code", "name", "description", "media_references", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        for field in ("company", "season"):
            obj = attrs.get(field, getattr(self.instance, field, None))
            if request and obj and obj.organization_id != request.user.organization_id:
                raise serializers.ValidationError({f"{field}_id": f"{field.title()} is outside the local organization."})
        return attrs


class FashionModelVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = FashionModelVariant
        fields = ("id", "code", "color", "size", "instructions", "media_references", "metadata", "is_active")
        read_only_fields = ("id",)


class FashionModelSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all(), allow_null=True, required=False)
    collection_id = serializers.PrimaryKeyRelatedField(source="collection", queryset=Collection.objects.all(), allow_null=True, required=False)
    variants = FashionModelVariantSerializer(many=True, required=False)

    class Meta:
        model = FashionModel
        fields = ("id", "organization_id", "company_id", "collection_id", "code", "name", "description", "instructions", "media_references", "metadata", "is_active", "variants", "created_at", "updated_at")
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        for field in ("company", "collection"):
            obj = attrs.get(field, getattr(self.instance, field, None))
            if request and obj and obj.organization_id != request.user.organization_id:
                raise serializers.ValidationError({f"{field}_id": f"{field.title()} is outside the local organization."})
        return attrs

    def create(self, validated_data):
        variants = validated_data.pop("variants", [])
        model = FashionModel.objects.create(**validated_data)
        FashionModelVariant.objects.bulk_create([FashionModelVariant(fashion_model=model, **item) for item in variants])
        return model


class FashionModelMaterialRequirementSerializer(serializers.ModelSerializer):
    model_variant_id = serializers.PrimaryKeyRelatedField(source="model_variant", queryset=FashionModelVariant.objects.all(), allow_null=True, required=False)
    product_id = serializers.PrimaryKeyRelatedField(source="product", queryset=Product.objects.all())
    product_variant_id = serializers.PrimaryKeyRelatedField(source="product_variant", queryset=ProductVariant.objects.all(), allow_null=True, required=False)
    unit_id = serializers.PrimaryKeyRelatedField(source="unit", queryset=UnitOfMeasure.objects.all())

    class Meta:
        model = FashionModelMaterialRequirement
        fields = ("id", "model_variant_id", "product_id", "product_variant_id", "quantity", "unit_id", "waste_rate", "notes", "position")
        read_only_fields = ("id",)

    def validate(self, attrs):
        fashion_model = self.context["fashion_model"]
        model_variant = attrs.get("model_variant")
        product = attrs["product"]
        product_variant = attrs.get("product_variant")
        unit = attrs["unit"]
        if model_variant and model_variant.fashion_model_id != fashion_model.id:
            raise serializers.ValidationError({"model_variant_id": "Variant is outside this fashion model."})
        if product.organization_id != fashion_model.organization_id:
            raise serializers.ValidationError({"product_id": "Product is outside the fashion model organization."})
        if product_variant and product_variant.product_id != product.id:
            raise serializers.ValidationError({"product_variant_id": "Product variant does not belong to the product."})
        if unit.organization_id != fashion_model.organization_id:
            raise serializers.ValidationError({"unit_id": "Unit is outside the fashion model organization."})
        if product.unit.category != unit.category:
            raise serializers.ValidationError({"unit_id": "Unit category must match the product unit category."})
        return attrs
