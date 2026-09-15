from rest_framework import serializers

from ivadoo.catalog.models import Product, ProductVariant
from ivadoo.internationalization.models import Currency, UnitOfMeasure
from ivadoo.organizations.models import Company

from .models import Supplier, SupplierAddress, SupplierContact, SupplierProduct


class SupplierContactSerializer(serializers.ModelSerializer):
    supplier_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = SupplierContact
        fields = ("id", "supplier_id", "name", "role", "email", "phone", "is_primary", "created_at", "updated_at")
        read_only_fields = ("id", "supplier_id", "created_at", "updated_at")


class SupplierAddressSerializer(serializers.ModelSerializer):
    supplier_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = SupplierAddress
        fields = ("id", "supplier_id", "label", "address_line1", "address_line2", "city", "region", "postal_code", "country_code", "is_primary", "created_at", "updated_at")
        read_only_fields = ("id", "supplier_id", "created_at", "updated_at")


class SupplierProductSerializer(serializers.ModelSerializer):
    supplier_id = serializers.UUIDField(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(source="product", queryset=Product.objects.all())
    product_variant_id = serializers.PrimaryKeyRelatedField(source="product_variant", queryset=ProductVariant.objects.all(), allow_null=True, required=False)
    unit_id = serializers.PrimaryKeyRelatedField(source="unit", queryset=UnitOfMeasure.objects.all())
    currency_code = serializers.PrimaryKeyRelatedField(source="currency", queryset=Currency.objects.all(), allow_null=True, required=False)

    class Meta:
        model = SupplierProduct
        fields = ("id", "supplier_id", "product_id", "product_variant_id", "unit_id", "currency_code", "supplier_sku", "lead_time_days", "minimum_quantity", "last_unit_price", "is_preferred", "created_at", "updated_at")
        read_only_fields = ("id", "supplier_id", "created_at", "updated_at")

    def validate(self, attrs):
        supplier = self.context["supplier"]
        product = attrs.get("product", getattr(self.instance, "product", None))
        variant = attrs.get("product_variant", getattr(self.instance, "product_variant", None))
        unit = attrs.get("unit", getattr(self.instance, "unit", None))
        if product.organization_id != supplier.organization_id:
            raise serializers.ValidationError({"product_id": "Product is outside the supplier organization."})
        if product.company_id and product.company_id != supplier.company_id:
            raise serializers.ValidationError({"product_id": "Company-specific product must match supplier company."})
        if variant and variant.product_id != product.id:
            raise serializers.ValidationError({"product_variant_id": "Variant must belong to the selected product."})
        if unit.organization_id != supplier.organization_id:
            raise serializers.ValidationError({"unit_id": "Unit is outside the supplier organization."})
        if product.unit.category != unit.category:
            raise serializers.ValidationError({"unit_id": "Unit category must match the product unit category."})
        return attrs


class SupplierSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all())
    currency_code = serializers.PrimaryKeyRelatedField(source="currency", queryset=Currency.objects.all(), allow_null=True, required=False)
    contacts = SupplierContactSerializer(many=True, read_only=True)
    addresses = SupplierAddressSerializer(many=True, read_only=True)
    products = SupplierProductSerializer(many=True, read_only=True)

    class Meta:
        model = Supplier
        fields = ("id", "organization_id", "company_id", "code", "name", "legal_name", "tax_identifier", "email", "phone", "website", "currency_code", "language_code", "lead_time_days", "minimum_order_amount", "notes", "status", "contacts", "addresses", "products", "created_at", "updated_at")
        read_only_fields = ("id", "organization_id", "created_at", "updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        company = attrs.get("company", getattr(self.instance, "company", None))
        if request and company.organization_id != request.user.organization_id:
            raise serializers.ValidationError({"company_id": "Company is outside the local organization."})
        return attrs
