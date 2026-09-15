import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from ivadoo.internationalization.constants import SUPPORTED_LANGUAGES
from ivadoo.internationalization.validators import validate_language_code


class Supplier(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        BLOCKED = "blocked", "Blocked"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="suppliers",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="suppliers",
    )
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    tax_identifier = models.CharField(max_length=128, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    website = models.URLField(blank=True)
    currency = models.ForeignKey(
        "internationalization.Currency",
        on_delete=models.PROTECT,
        related_name="purchase_suppliers",
        null=True,
        blank=True,
    )
    language_code = models.CharField(
        max_length=8,
        choices=SUPPORTED_LANGUAGES,
        default="fr",
        validators=[validate_language_code],
    )
    lead_time_days = models.PositiveIntegerField(default=0)
    minimum_order_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="purchase_supplier_unique_code_org",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.company_id
            and self.organization_id
            and self.company.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"company": "Company must belong to the supplier organization."}
            )

    def __str__(self):
        return self.name


class SupplierContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_primary", "name")

    def __str__(self):
        return self.name


class SupplierAddress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    label = models.CharField(max_length=120, blank=True)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    region = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=32, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_primary", "label", "city")

    def __str__(self):
        return self.label or self.address_line1


class SupplierProduct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="products",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="supplier_links",
    )
    product_variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="supplier_links",
        null=True,
        blank=True,
    )
    unit = models.ForeignKey(
        "internationalization.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="supplier_products",
    )
    currency = models.ForeignKey(
        "internationalization.Currency",
        on_delete=models.PROTECT,
        related_name="supplier_products",
        null=True,
        blank=True,
    )
    supplier_sku = models.CharField(max_length=96, blank=True)
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    minimum_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    last_unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    is_preferred = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("supplier__name", "product__name")
        constraints = [
            models.UniqueConstraint(
                fields=("supplier", "product"),
                condition=models.Q(product_variant__isnull=True),
                name="purchase_supplier_product_unique_base",
            ),
            models.UniqueConstraint(
                fields=("supplier", "product_variant"),
                condition=models.Q(product_variant__isnull=False),
                name="purchase_supplier_product_unique_variant",
            ),
        ]

    def clean(self):
        super().clean()
        organization_id = self.supplier.organization_id
        if self.product.organization_id != organization_id:
            raise ValidationError(
                {"product": "Product is outside the supplier organization."}
            )
        if (
            self.product.company_id
            and self.product.company_id != self.supplier.company_id
        ):
            raise ValidationError(
                {"product": "Company-specific product must match supplier company."}
            )
        if (
            self.product_variant_id
            and self.product_variant.product_id != self.product_id
        ):
            raise ValidationError(
                {"product_variant": "Variant must belong to the selected product."}
            )
        if self.unit.organization_id != organization_id:
            raise ValidationError(
                {"unit": "Unit is outside the supplier organization."}
            )
        if self.product.unit.category != self.unit.category:
            raise ValidationError(
                {"unit": "Unit category must match the product unit category."}
            )

    def __str__(self):
        return f"{self.supplier} · {self.product}"


from .procurement_models import (  # noqa: E402,F401
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    RequestForQuotation,
    RFQSupplier,
    SupplierQuotation,
    SupplierQuotationLine,
)
from .receipt_models import (  # noqa: E402,F401
    PurchaseReceipt,
    PurchaseReceiptLine,
    SupplierPurchaseHistory,
)
