import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class WorkCenter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="manufacturing_work_centers",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="manufacturing_work_centers",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="manufacturing_work_centers",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company__name", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"),
                name="manufacturing_work_center_unique_code_company",
            ),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the work center organization."})
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError({"establishment": "Establishment must belong to the work center company."})

    def __str__(self):
        return self.name


class ManufacturingOperation(models.Model):
    class OperationType(models.TextChoices):
        CUTTING = "cutting", "Cutting"
        SEWING = "sewing", "Sewing"
        EMBROIDERY = "embroidery", "Embroidery"
        DYEING = "dyeing", "Dyeing"
        FINISHING = "finishing", "Finishing"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"
        REWORK = "rework", "Rework"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="manufacturing_operations",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="manufacturing_operations",
    )
    manufacturing_order = models.ForeignKey(
        "manufacturing.ManufacturingOrder",
        on_delete=models.PROTECT,
        related_name="operations",
    )
    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.PROTECT,
        related_name="operations",
        null=True,
        blank=True,
    )
    operation_type = models.CharField(max_length=24, choices=OperationType.choices)
    name = models.CharField(max_length=160)
    position = models.PositiveIntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    planned_minutes = models.PositiveIntegerField(default=0)
    actual_minutes = models.PositiveIntegerField(default=0)
    planned_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    processed_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    rework_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_manufacturing_operations",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("manufacturing_order", "position", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("manufacturing_order", "position"),
                name="manufacturing_operation_unique_position_order",
            ),
            models.CheckConstraint(
                condition=models.Q(planned_quantity__gt=0),
                name="manufacturing_operation_planned_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(processed_quantity__gte=0),
                name="manufacturing_operation_processed_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(processed_quantity__lte=models.F("planned_quantity")),
                name="manufacturing_operation_processed_lte_planned",
            ),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the operation organization."})
        if self.manufacturing_order_id:
            if self.manufacturing_order.organization_id != self.organization_id:
                raise ValidationError({"manufacturing_order": "Manufacturing order is outside the operation organization."})
            if self.manufacturing_order.company_id != self.company_id:
                raise ValidationError({"manufacturing_order": "Manufacturing order must belong to the operation company."})
        if self.work_center_id:
            if self.work_center.organization_id != self.organization_id:
                raise ValidationError({"work_center": "Work center is outside the operation organization."})
            if self.work_center.company_id != self.company_id:
                raise ValidationError({"work_center": "Work center must belong to the operation company."})
        if self.processed_quantity > self.planned_quantity:
            raise ValidationError({"processed_quantity": "Processed quantity cannot exceed planned quantity."})
        if self.completed_at and self.started_at and self.completed_at < self.started_at:
            raise ValidationError({"completed_at": "Completion cannot precede the operation start."})

    def __str__(self):
        return f"{self.manufacturing_order.number} · {self.position} · {self.name}"


class ManufacturingOperationTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation = models.ForeignKey(
        ManufacturingOperation,
        on_delete=models.PROTECT,
        related_name="history",
    )
    from_status = models.CharField(max_length=16)
    to_status = models.CharField(max_length=16)
    action = models.CharField(max_length=24)
    reason = models.CharField(max_length=255, blank=True)
    sequence_override = models.BooleanField(default=False)
    processed_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
    )
    actual_minutes = models.PositiveIntegerField(default=0)
    actor = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="manufacturing_operation_transitions",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("occurred_at", "id")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Manufacturing operation transition history is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Manufacturing operation transition history is immutable.")
