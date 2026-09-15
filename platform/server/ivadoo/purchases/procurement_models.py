import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class PurchaseRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="purchase_requests")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="purchase_requests")
    establishment = models.ForeignKey("organizations.Establishment", on_delete=models.PROTECT, related_name="purchase_requests", null=True, blank=True)
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT, related_name="purchase_requests", null=True, blank=True)
    order = models.ForeignKey("sales.Order", on_delete=models.PROTECT, related_name="purchase_requests", null=True, blank=True)
    number = models.CharField(max_length=64)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    needed_by = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    transition_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="created_purchase_requests")
    approved_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="approved_purchase_requests", null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("organization", "number"), name="purchase_request_unique_number_org")]

    def clean(self):
        super().clean()
        if self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the request organization."})
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError({"establishment": "Establishment must belong to the request company."})
        if self.warehouse_id and self.warehouse.company_id != self.company_id:
            raise ValidationError({"warehouse": "Warehouse must belong to the request company."})
        if self.order_id and (self.order.organization_id != self.organization_id or self.order.company_id != self.company_id):
            raise ValidationError({"order": "Order must belong to the request organization and company."})

    def __str__(self):
        return self.number


class PurchaseRequestLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="purchase_request_lines")
    product_variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="purchase_request_lines", null=True, blank=True)
    unit = models.ForeignKey("internationalization.UnitOfMeasure", on_delete=models.PROTECT, related_name="purchase_request_lines")
    quantity = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])
    need_reference_type = models.CharField(max_length=80, blank=True)
    need_reference_id = models.UUIDField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("id",)


class RequestForQuotation(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="purchase_rfqs")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="purchase_rfqs")
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.PROTECT, related_name="rfqs", null=True, blank=True)
    number = models.CharField(max_length=64)
    currency = models.ForeignKey("internationalization.Currency", on_delete=models.PROTECT, related_name="purchase_rfqs")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    transition_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="created_purchase_rfqs")
    sent_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("organization", "number"), name="purchase_rfq_unique_number_org")]

    def __str__(self):
        return self.number


class RFQSupplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rfq = models.ForeignKey(RequestForQuotation, on_delete=models.CASCADE, related_name="supplier_links")
    supplier = models.ForeignKey("purchases.Supplier", on_delete=models.PROTECT, related_name="rfq_links")
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("rfq", "supplier"), name="purchase_rfq_unique_supplier")]


class SupplierQuotation(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        SELECTED = "selected", "Selected"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rfq = models.ForeignKey(RequestForQuotation, on_delete=models.PROTECT, related_name="quotations")
    supplier = models.ForeignKey("purchases.Supplier", on_delete=models.PROTECT, related_name="quotations")
    quote_number = models.CharField(max_length=96, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED)
    quoted_at = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        constraints = [models.UniqueConstraint(fields=("rfq", "supplier"), name="purchase_quote_unique_supplier_rfq")]


class SupplierQuotationLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation = models.ForeignKey(SupplierQuotation, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="supplier_quotation_lines")
    product_variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="supplier_quotation_lines", null=True, blank=True)
    unit = models.ForeignKey("internationalization.UnitOfMeasure", on_delete=models.PROTECT, related_name="supplier_quotation_lines")
    quantity = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal("0"))])
    lead_time_days = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("id",)


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_APPROVAL = "pending_approval", "Pending approval"
        APPROVED = "approved", "Approved"
        ORDERED = "ordered", "Ordered"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="purchase_orders")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="purchase_orders")
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT, related_name="purchase_orders", null=True, blank=True)
    supplier = models.ForeignKey("purchases.Supplier", on_delete=models.PROTECT, related_name="purchase_orders")
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.PROTECT, related_name="purchase_orders", null=True, blank=True)
    rfq = models.ForeignKey(RequestForQuotation, on_delete=models.PROTECT, related_name="purchase_orders", null=True, blank=True)
    quotation = models.ForeignKey(SupplierQuotation, on_delete=models.PROTECT, related_name="purchase_orders", null=True, blank=True)
    currency = models.ForeignKey("internationalization.Currency", on_delete=models.PROTECT, related_name="purchase_orders")
    number = models.CharField(max_length=64)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    transition_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="created_purchase_orders")
    approved_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="approved_purchase_orders", null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    ordered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("organization", "number"), name="purchase_order_unique_number_org")]

    def __str__(self):
        return self.number


class PurchaseOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="purchase_order_lines")
    product_variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="purchase_order_lines", null=True, blank=True)
    unit = models.ForeignKey("internationalization.UnitOfMeasure", on_delete=models.PROTECT, related_name="purchase_order_lines")
    quantity = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal("0"))])
    expected_date = models.DateField(null=True, blank=True)
    received_quantity = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))])

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(condition=models.Q(received_quantity__gte=0), name="purchase_order_line_received_nonnegative"),
            models.CheckConstraint(condition=models.Q(received_quantity__lte=models.F("quantity")), name="purchase_order_line_received_lte_ordered"),
        ]
