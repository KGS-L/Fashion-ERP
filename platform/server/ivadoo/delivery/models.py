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
