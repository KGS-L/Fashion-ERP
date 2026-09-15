import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Product(models.Model):
    class ProductType(models.TextChoices):
        FINISHED_GOOD = "finished_good", "Finished good"
        FABRIC = "fabric", "Fabric"
        ACCESSORY = "accessory", "Accessory"
        SERVICE = "service", "Service"
        PACKAGING = "packaging", "Packaging"
        WASTE = "waste", "Waste"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="products")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="products", null=True, blank=True)
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    product_type = models.CharField(max_length=24, choices=ProductType.choices)
    unit = models.ForeignKey("internationalization.UnitOfMeasure", on_delete=models.PROTECT, related_name="products")
    fashion_metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("organization", "code"), name="product_unique_code_per_org")]
        ordering = ("name",)

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company must belong to the organization."})
        if self.unit_id and self.unit.organization_id != self.organization_id:
            raise ValidationError({"unit": "Unit must belong to the organization."})


class ProductAttribute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="product_attributes")
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("organization", "code"), name="product_attribute_unique_code_per_org")]
        ordering = ("name",)


class ProductAttributeValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE, related_name="values")
    code = models.SlugField(max_length=80)
    value = models.CharField(max_length=160)
    position = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("attribute", "code"), name="product_attribute_value_unique_code")]
        ordering = ("position", "value")


class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=96)
    barcode = models.CharField(max_length=128, blank=True)
    name = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    attribute_values = models.ManyToManyField(ProductAttributeValue, through="ProductVariantAttributeValue", related_name="variants")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("product", "sku"), name="product_variant_unique_sku_per_product"),
            models.UniqueConstraint(fields=("product", "barcode"), condition=~models.Q(barcode=""), name="product_variant_unique_barcode_per_product"),
        ]
        ordering = ("sku",)


class ProductVariantAttributeValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="variant_attribute_values")
    attribute_value = models.ForeignKey(ProductAttributeValue, on_delete=models.PROTECT, related_name="variant_attribute_values")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("variant", "attribute_value"), name="variant_unique_attribute_value"),
        ]

    def clean(self):
        super().clean()
        if self.variant_id and self.attribute_value_id:
            if self.variant.product.organization_id != self.attribute_value.attribute.organization_id:
                raise ValidationError({"attribute_value": "Attribute value must belong to the product organization."})
