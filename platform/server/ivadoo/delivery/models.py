import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Delivery(models.Model):
    class Mode(models.TextChoices):
        PICKUP = "pickup", "Pickup"
        LOCAL_DELIVERY = "local_delivery", "Local delivery"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PREPARED = "prepared", "Prepared"
        ASSIGNED = "assigned", "Assigned"
        SHIPPED = "shipped", "Shipped"
        READY_FOR_PICKUP = "ready_for_pickup", "Ready for pickup"
        PICKED_UP = "picked_up", "Picked up"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="deliveries")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="deliveries")
    order = models.ForeignKey("sales.Order", on_delete=models.PROTECT, related_name="deliveries")
    number = models.CharField(max_length=64)
    mode = models.CharField(max_length=24, choices=Mode.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    courier_name = models.CharField(max_length=160, blank=True)
    courier_reference = models.CharField(max_length=160, blank=True)
    destination_notes = models.TextField(blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="created_deliveries")
    prepared_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("organization", "number"), name="delivery_unique_number_org"),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the delivery organization."})
        if self.order_id and (self.order.organization_id != self.organization_id or self.order.company_id != self.company_id):
            raise ValidationError({"order": "Order is outside the delivery scope."})
        if self.mode == self.Mode.PICKUP and (self.courier_name or self.courier_reference):
            raise ValidationError({"courier_name": "Pickup deliveries cannot have a courier assignment."})


class DeliveryLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="lines")
    order_line = models.ForeignKey("sales.OrderLine", on_delete=models.PROTECT, related_name="delivery_lines")
    quantity = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])

    class Meta:
        ordering = ("order_line_id",)
        constraints = [
            models.UniqueConstraint(fields=("delivery", "order_line"), name="delivery_unique_order_line"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="delivery_line_quantity_positive"),
        ]

    def clean(self):
        super().clean()
        if self.order_line_id and self.delivery_id and self.order_line.order_id != self.delivery.order_id:
            raise ValidationError({"order_line": "Order line must belong to the delivery order."})


class DeliveryPackage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="packages")
    code = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    is_sealed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("code",)
        constraints = [models.UniqueConstraint(fields=("delivery", "code"), name="delivery_package_unique_code")]


class DeliveryProof(models.Model):
    class ProofType(models.TextChoices):
        RECIPIENT_ACK = "recipient_ack", "Recipient acknowledgement"
        SIGNATURE = "signature", "Signature"
        PHOTO = "photo", "Photo"
        CODE = "code", "Code"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.OneToOneField(Delivery, on_delete=models.PROTECT, related_name="proof")
    proof_type = models.CharField(max_length=24, choices=ProofType.choices)
    recipient_name = models.CharField(max_length=160)
    evidence_reference = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="recorded_delivery_proofs")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-recorded_at",)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Delivery proofs are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Delivery proofs are immutable.")


class DeliveryReturn(models.Model):
    class Resolution(models.TextChoices):
        RETURN_ONLY = "return_only", "Return only"
        EXCHANGE = "exchange", "Exchange"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="delivery_returns")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="delivery_returns")
    delivery = models.ForeignKey(Delivery, on_delete=models.PROTECT, related_name="returns")
    number = models.CharField(max_length=64)
    reason = models.TextField()
    resolution = models.CharField(max_length=24, choices=Resolution.choices, default=Resolution.RETURN_ONLY)
    idempotency_key = models.CharField(max_length=160)
    created_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="created_delivery_returns")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("organization", "number"), name="delivery_return_unique_number_org"),
            models.UniqueConstraint(fields=("organization", "idempotency_key"), name="delivery_return_unique_idempotency_org"),
        ]

    def clean(self):
        super().clean()
        if self.delivery_id and (
            self.delivery.organization_id != self.organization_id
            or self.delivery.company_id != self.company_id
        ):
            raise ValidationError({"delivery": "Delivery return is outside the delivery scope."})
        if not self.reason.strip():
            raise ValidationError({"reason": "Return reason is required."})
        if not self.idempotency_key.strip():
            raise ValidationError({"idempotency_key": "Idempotency key is required."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Delivery returns are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Delivery returns are immutable.")


class DeliveryReturnLine(models.Model):
    class Disposition(models.TextChoices):
        RESTOCK = "restock", "Restock"
        QUARANTINE = "quarantine", "Quarantine"
        DAMAGED = "damaged", "Damaged"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery_return = models.ForeignKey(DeliveryReturn, on_delete=models.PROTECT, related_name="lines")
    delivery_line = models.ForeignKey(DeliveryLine, on_delete=models.PROTECT, related_name="return_lines")
    quantity = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])
    disposition = models.CharField(max_length=24, choices=Disposition.choices)
    destination_location = models.ForeignKey(
        "inventory.StockLocation",
        on_delete=models.PROTECT,
        related_name="delivery_return_lines",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(fields=("delivery_return", "delivery_line"), name="delivery_return_unique_delivery_line"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="delivery_return_line_quantity_positive"),
        ]

    def clean(self):
        super().clean()
        if self.delivery_line_id and self.delivery_return_id:
            if self.delivery_line.delivery_id != self.delivery_return.delivery_id:
                raise ValidationError({"delivery_line": "Returned line must belong to the selected delivery."})
        if self.destination_location_id:
            if self.destination_location.organization_id != self.delivery_return.organization_id:
                raise ValidationError({"destination_location": "Return destination is outside the organization."})
            if self.destination_location.company_id != self.delivery_return.company_id:
                raise ValidationError({"destination_location": "Return destination is outside the company."})
        if self.disposition == self.Disposition.QUARANTINE:
            if not self.destination_location_id:
                raise ValidationError({"destination_location": "Quarantine requires an explicit receiving location."})
            if self.destination_location.kind != self.destination_location.Kind.RECEIVING:
                raise ValidationError({"destination_location": "Quarantine must use a receiving location reserved for quarantine."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Delivery return lines are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Delivery return lines are immutable.")


class DeliveryReturnStockAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    return_line = models.ForeignKey(DeliveryReturnLine, on_delete=models.PROTECT, related_name="stock_allocations")
    delivery_issue_movement = models.ForeignKey(
        "inventory.StockMovement",
        on_delete=models.PROTECT,
        related_name="delivery_return_source_allocations",
    )
    return_movement = models.OneToOneField(
        "inventory.StockMovement",
        on_delete=models.PROTECT,
        related_name="delivery_return_allocation",
    )
    damage_movement = models.OneToOneField(
        "inventory.StockMovement",
        on_delete=models.PROTECT,
        related_name="delivery_return_damage_allocation",
        null=True,
        blank=True,
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("return_line", "delivery_issue_movement"),
                name="delivery_return_unique_source_movement",
            ),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="delivery_return_allocation_quantity_positive"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Delivery return stock allocations are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Delivery return stock allocations are immutable.")
