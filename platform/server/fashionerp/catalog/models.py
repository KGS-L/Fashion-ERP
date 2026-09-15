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


class Season(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="fashion_seasons")
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("organization", "code"), name="fashion_season_unique_code_per_org")]
        ordering = ("-year", "name")

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot precede start date."})


class Collection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="fashion_collections")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="fashion_collections", null=True, blank=True)
    season = models.ForeignKey(Season, on_delete=models.PROTECT, related_name="collections", null=True, blank=True)
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    media_references = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("organization", "code"), name="fashion_collection_unique_code_per_org")]
        ordering = ("name",)

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company must belong to the organization."})
        if self.season_id and self.season.organization_id != self.organization_id:
            raise ValidationError({"season": "Season must belong to the organization."})


class FashionModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="fashion_models")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="fashion_models", null=True, blank=True)
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT, related_name="models", null=True, blank=True)
    code = models.CharField(max_length=80)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    media_references = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("organization", "code"), name="fashion_model_unique_code_per_org")]
        ordering = ("name",)

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company must belong to the organization."})
        if self.collection_id and self.collection.organization_id != self.organization_id:
            raise ValidationError({"collection": "Collection must belong to the organization."})


class FashionModelVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fashion_model = models.ForeignKey(FashionModel, on_delete=models.CASCADE, related_name="variants")
    code = models.CharField(max_length=96)
    color = models.CharField(max_length=120, blank=True)
    size = models.CharField(max_length=80, blank=True)
    instructions = models.TextField(blank=True)
    media_references = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("fashion_model", "code"), name="fashion_model_variant_unique_code")]
        ordering = ("code",)


class FashionModelMaterialRequirement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fashion_model = models.ForeignKey(FashionModel, on_delete=models.CASCADE, related_name="material_requirements")
    model_variant = models.ForeignKey(FashionModelVariant, on_delete=models.CASCADE, related_name="material_requirements", null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="fashion_model_requirements")
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="fashion_model_requirements", null=True, blank=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit = models.ForeignKey("internationalization.UnitOfMeasure", on_delete=models.PROTECT, related_name="fashion_model_requirements")
    waste_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    notes = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="fashion_requirement_positive_quantity"),
            models.CheckConstraint(condition=models.Q(waste_rate__gte=0), name="fashion_requirement_nonnegative_waste"),
            models.UniqueConstraint(
                fields=("fashion_model", "model_variant", "product", "product_variant"),
                name="fashion_requirement_unique_material",
            ),
        ]
        ordering = ("position", "product__name")

    def clean(self):
        super().clean()
        organization_id = self.fashion_model.organization_id if self.fashion_model_id else None
        if self.model_variant_id and self.model_variant.fashion_model_id != self.fashion_model_id:
            raise ValidationError({"model_variant": "Model variant must belong to the fashion model."})
        if self.product_id and self.product.organization_id != organization_id:
            raise ValidationError({"product": "Product must belong to the fashion model organization."})
        if self.product_variant_id and self.product_variant.product_id != self.product_id:
            raise ValidationError({"product_variant": "Product variant must belong to the selected product."})
        if self.unit_id and self.unit.organization_id != organization_id:
            raise ValidationError({"unit": "Unit must belong to the fashion model organization."})
        if self.product_id and self.unit_id and self.product.unit.category != self.unit.category:
            raise ValidationError({"unit": "Unit category must match the product unit category."})
