import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Quotation(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="quotations",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="quotations",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="quotations",
    )
    currency = models.ForeignKey(
        "internationalization.Currency",
        on_delete=models.PROTECT,
        related_name="quotations",
    )
    number = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "number"),
                name="quotation_unique_number_org",
            )
        ]


class QuotationLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    fashion_model = models.ForeignKey(
        "catalog.FashionModel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quotation_lines",
    )
    model_variant = models.ForeignKey(
        "catalog.FashionModelVariant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quotation_lines",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=4)
    discount_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="quotation_line_positive_quantity",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="quotation_line_nonnegative_unit_price",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_rate__gte=0)
                & models.Q(discount_rate__lte=1),
                name="quotation_line_discount_rate_range",
            ),
        ]


class Order(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    class OrderType(models.TextChoices):
        CUSTOM = "custom", "Custom"
        SERIES = "series", "Series"
        WHOLESALE = "wholesale", "Wholesale"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="fashion_orders",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="fashion_orders",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="fashion_orders",
    )
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_fashion_orders",
    )
    number = models.CharField(max_length=64)
    order_type = models.CharField(
        max_length=16,
        choices=OrderType.choices,
        default=OrderType.CUSTOM,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    delivery_date = models.DateField(null=True, blank=True)
    event_date = models.DateField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "number"),
                name="fashion_order_unique_number_org",
            )
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the order organization."})
        if self.customer_id and (
            self.customer.organization_id != self.organization_id
            or self.customer.company_id != self.company_id
        ):
            raise ValidationError({"customer": "Customer is outside the order scope."})
        if self.quotation_id and (
            self.quotation.organization_id != self.organization_id
            or self.quotation.company_id != self.company_id
            or self.quotation.customer_id != self.customer_id
        ):
            raise ValidationError({"quotation": "Quotation is outside the order scope."})
        if self.created_by_id and self.created_by.organization_id != self.organization_id:
            raise ValidationError({"created_by": "Order creator is outside the organization."})
        if self.delivery_date and self.event_date and self.delivery_date > self.event_date:
            raise ValidationError(
                {"event_date": "Event date cannot be earlier than the delivery date."}
            )


class OrderLine(models.Model):
    class FulfillmentMode(models.TextChoices):
        AUTO = "auto", "Automatic"
        FINISHED_STOCK = "finished_stock", "Finished stock"
        PRODUCTION = "production", "Production"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    fashion_model = models.ForeignKey(
        "catalog.FashionModel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_lines",
    )
    model_variant = models.ForeignKey(
        "catalog.FashionModelVariant",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_lines",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=4)
    discount_rate = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    fulfillment_mode = models.CharField(
        max_length=24,
        choices=FulfillmentMode.choices,
        default=FulfillmentMode.AUTO,
    )
    commercial_customization = models.JSONField(default=dict, blank=True)
    measurement_set = models.ForeignKey(
        "measurements.MeasurementSet",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_lines",
    )
    measurement_snapshot = models.JSONField(default=dict, blank=True)
    measurement_source_version = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_line_positive_quantity",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="order_line_nonnegative_unit_price",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_rate__gte=0)
                & models.Q(discount_rate__lte=1),
                name="order_line_discount_rate_range",
            ),
        ]


class OrderLineVariantQuantity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_line = models.ForeignKey(
        OrderLine,
        on_delete=models.CASCADE,
        related_name="variant_quantities",
    )
    model_variant = models.ForeignKey(
        "catalog.FashionModelVariant",
        on_delete=models.PROTECT,
        related_name="order_line_quantities",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    commercial_customization = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("model_variant__code",)
        constraints = [
            models.UniqueConstraint(
                fields=("order_line", "model_variant"),
                name="order_line_variant_quantity_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_line_variant_quantity_positive",
            ),
        ]

    def clean(self):
        super().clean()
        if self.order_line_id and self.model_variant_id:
            line = self.order_line
            if not line.fashion_model_id:
                raise ValidationError(
                    {"model_variant": "Variant quantities require a fashion model on the order line."}
                )
            if self.model_variant.fashion_model_id != line.fashion_model_id:
                raise ValidationError(
                    {"model_variant": "Variant must belong to the order-line fashion model."}
                )


class OrderCommercialSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="commercial_snapshot",
    )
    order_type = models.CharField(max_length=16, choices=Order.OrderType.choices)
    subtotal = models.DecimalField(max_digits=18, decimal_places=4)
    discount_total = models.DecimalField(max_digits=18, decimal_places=4)
    total = models.DecimalField(max_digits=18, decimal_places=4)
    payload = models.JSONField(default=dict)
    confirmed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="confirmed_order_commercial_snapshots",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="order_commercial_snapshot_subtotal_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_total__gte=0),
                name="order_commercial_snapshot_discount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name="order_commercial_snapshot_total_nonnegative",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Confirmed commercial snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Confirmed commercial snapshots are immutable.")


from .fitting_models import AlterationRequest, CustomerValidation, FittingSession  # noqa: E402,F401
