import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class PurchaseReceipt(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONTROLLED = "controlled", "Controlled"
        POSTED = "posted", "Posted"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="purchase_receipts",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="purchase_receipts",
    )
    purchase_order = models.ForeignKey(
        "purchases.PurchaseOrder",
        on_delete=models.PROTECT,
        related_name="receipts",
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="purchase_receipts",
    )
    number = models.CharField(max_length=64)
    supplier_delivery_reference = models.CharField(max_length=128, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField(blank=True)
    transition_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_purchase_receipts",
    )
    controlled_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="controlled_purchase_receipts",
        null=True,
        blank=True,
    )
    posted_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="posted_purchase_receipts",
        null=True,
        blank=True,
    )
    controlled_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-received_at", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "number"),
                name="purchase_receipt_unique_number_org",
            )
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the receipt organization."})
        if self.purchase_order_id:
            if self.purchase_order.organization_id != self.organization_id:
                raise ValidationError({"purchase_order": "Purchase order is outside the receipt organization."})
            if self.purchase_order.company_id != self.company_id:
                raise ValidationError({"purchase_order": "Purchase order must belong to the receipt company."})
        if self.warehouse_id:
            if self.warehouse.organization_id != self.organization_id or self.warehouse.company_id != self.company_id:
                raise ValidationError({"warehouse": "Warehouse is outside the receipt company."})
            if self.purchase_order_id and self.purchase_order.warehouse_id and self.purchase_order.warehouse_id != self.warehouse_id:
                raise ValidationError({"warehouse": "Warehouse must match the purchase order warehouse."})

    def __str__(self):
        return self.number


class PurchaseReceiptLine(models.Model):
    class QualityStatus(models.TextChoices):
        PENDING = "pending", "Pending control"
        ACCEPTED = "accepted", "Accepted"
        PARTIAL = "partial", "Partially accepted"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.ForeignKey(
        PurchaseReceipt,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    purchase_order_line = models.ForeignKey(
        "purchases.PurchaseOrderLine",
        on_delete=models.PROTECT,
        related_name="receipt_lines",
    )
    location = models.ForeignKey(
        "inventory.StockLocation",
        on_delete=models.PROTECT,
        related_name="purchase_receipt_lines",
    )
    received_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    accepted_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    rejected_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    quality_status = models.CharField(
        max_length=16,
        choices=QualityStatus.choices,
        default=QualityStatus.PENDING,
    )
    control_note = models.CharField(max_length=255, blank=True)
    stock_movement = models.ForeignKey(
        "inventory.StockMovement",
        on_delete=models.PROTECT,
        related_name="purchase_receipt_lines",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("receipt", "purchase_order_line"),
                name="purchase_receipt_unique_order_line",
            ),
            models.CheckConstraint(
                condition=models.Q(received_quantity__gt=0),
                name="purchase_receipt_line_received_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(accepted_quantity__gte=0),
                name="purchase_receipt_line_accepted_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(rejected_quantity__gte=0),
                name="purchase_receipt_line_rejected_nonnegative",
            ),
        ]

    def clean(self):
        super().clean()
        if self.receipt_id and self.purchase_order_line_id:
            if self.purchase_order_line.purchase_order_id != self.receipt.purchase_order_id:
                raise ValidationError({"purchase_order_line": "Line must belong to the receipt purchase order."})
        if self.receipt_id and self.location_id and self.location.warehouse_id != self.receipt.warehouse_id:
            raise ValidationError({"location": "Location must belong to the receipt warehouse."})
        if self.accepted_quantity + self.rejected_quantity > self.received_quantity:
            raise ValidationError("Accepted plus rejected quantity cannot exceed received quantity.")


class SupplierPurchaseHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_line = models.OneToOneField(
        PurchaseReceiptLine,
        on_delete=models.PROTECT,
        related_name="supplier_history",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="supplier_purchase_history",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="supplier_purchase_history",
    )
    supplier = models.ForeignKey(
        "purchases.Supplier",
        on_delete=models.PROTECT,
        related_name="purchase_history",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="supplier_purchase_history",
    )
    product_variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="supplier_purchase_history",
        null=True,
        blank=True,
    )
    unit = models.ForeignKey(
        "internationalization.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="supplier_purchase_history",
    )
    currency = models.ForeignKey(
        "internationalization.Currency",
        on_delete=models.PROTECT,
        related_name="supplier_purchase_history",
    )
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    ordered_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    received_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    accepted_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    rejected_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    expected_date = models.DateField(null=True, blank=True)
    received_at = models.DateTimeField()
    ordered_at = models.DateTimeField(null=True, blank=True)
    lead_time_days = models.PositiveIntegerField(default=0)
    on_time = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-received_at", "-created_at")
        indexes = [
            models.Index(
                fields=("organization", "supplier", "received_at"),
                name="purchase_supplier_history_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Supplier purchase history is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Supplier purchase history is immutable.")
