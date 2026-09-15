import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class QualityInspection(models.Model):
    class InspectionType(models.TextChoices):
        RECEIVING = "receiving", "Receiving"
        IN_PROCESS = "in_process", "In process"
        FINAL = "final", "Final"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"

    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPT = "accept", "Accept"
        REJECT = "reject", "Reject"
        REWORK = "rework", "Rework"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="quality_inspections",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="quality_inspections",
    )
    inspection_type = models.CharField(max_length=16, choices=InspectionType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    decision = models.CharField(max_length=16, choices=Decision.choices, default=Decision.PENDING)
    blocking = models.BooleanField(default=True)
    purchase_receipt_line = models.ForeignKey(
        "purchases.PurchaseReceiptLine",
        on_delete=models.PROTECT,
        related_name="quality_inspections",
        null=True,
        blank=True,
    )
    manufacturing_order = models.ForeignKey(
        "manufacturing.ManufacturingOrder",
        on_delete=models.PROTECT,
        related_name="quality_inspections",
        null=True,
        blank=True,
    )
    manufacturing_operation = models.ForeignKey(
        "manufacturing.ManufacturingOperation",
        on_delete=models.PROTECT,
        related_name="quality_inspections",
        null=True,
        blank=True,
    )
    output_receipt = models.ForeignKey(
        "manufacturing.ManufacturingOutputReceipt",
        on_delete=models.PROTECT,
        related_name="quality_inspections",
        null=True,
        blank=True,
    )
    parent_inspection = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="reinspections",
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    completion_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_quality_inspections",
    )
    completed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="completed_quality_inspections",
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(purchase_receipt_line__isnull=False, manufacturing_order__isnull=True, manufacturing_operation__isnull=True, output_receipt__isnull=True)
                    | models.Q(purchase_receipt_line__isnull=True, manufacturing_order__isnull=False, manufacturing_operation__isnull=True, output_receipt__isnull=True)
                    | models.Q(purchase_receipt_line__isnull=True, manufacturing_order__isnull=True, manufacturing_operation__isnull=False, output_receipt__isnull=True)
                    | models.Q(purchase_receipt_line__isnull=True, manufacturing_order__isnull=True, manufacturing_operation__isnull=True, output_receipt__isnull=False)
                ),
                name="quality_inspection_exactly_one_context",
            ),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the inspection organization."})
        if self.purchase_receipt_line_id:
            receipt = self.purchase_receipt_line.receipt
            if receipt.organization_id != self.organization_id or receipt.company_id != self.company_id:
                raise ValidationError({"purchase_receipt_line": "Receipt line is outside the inspection scope."})
            if self.inspection_type != self.InspectionType.RECEIVING:
                raise ValidationError({"inspection_type": "Receipt-line inspections must use receiving type."})
        if self.manufacturing_order_id:
            if self.manufacturing_order.organization_id != self.organization_id or self.manufacturing_order.company_id != self.company_id:
                raise ValidationError({"manufacturing_order": "Manufacturing order is outside the inspection scope."})
            if self.inspection_type == self.InspectionType.RECEIVING:
                raise ValidationError({"inspection_type": "Manufacturing inspections cannot use receiving type."})
        if self.manufacturing_operation_id:
            operation = self.manufacturing_operation
            if operation.organization_id != self.organization_id or operation.company_id != self.company_id:
                raise ValidationError({"manufacturing_operation": "Manufacturing operation is outside the inspection scope."})
            if self.inspection_type != self.InspectionType.IN_PROCESS:
                raise ValidationError({"inspection_type": "Operation inspections must use in-process type."})
        if self.output_receipt_id:
            receipt = self.output_receipt
            if receipt.organization_id != self.organization_id or receipt.company_id != self.company_id:
                raise ValidationError({"output_receipt": "Output receipt is outside the inspection scope."})
            if self.inspection_type != self.InspectionType.FINAL:
                raise ValidationError({"inspection_type": "Finished-output inspections must use final type."})
        if self.parent_inspection_id:
            parent = self.parent_inspection
            if parent.organization_id != self.organization_id or parent.company_id != self.company_id:
                raise ValidationError({"parent_inspection": "Parent inspection is outside the local scope."})
            if parent.status != self.Status.COMPLETED or parent.decision != self.Decision.REWORK:
                raise ValidationError({"parent_inspection": "A reinspection must follow a completed rework decision."})
            context_fields = ("purchase_receipt_line_id", "manufacturing_order_id", "manufacturing_operation_id", "output_receipt_id")
            if any(getattr(parent, field) != getattr(self, field) for field in context_fields):
                raise ValidationError({"parent_inspection": "Reinspection context must match the parent inspection."})

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("status").first()
            if previous and previous["status"] == self.Status.COMPLETED:
                raise ValidationError("Completed quality inspections are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.COMPLETED:
            raise ValidationError("Completed quality inspections are immutable.")
        return super().delete(*args, **kwargs)


class QualityCriterion(models.Model):
    class Result(models.TextChoices):
        PENDING = "pending", "Pending"
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        NOT_APPLICABLE = "not_applicable", "Not applicable"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection = models.ForeignKey(QualityInspection, on_delete=models.CASCADE, related_name="criteria")
    code = models.CharField(max_length=64)
    label = models.CharField(max_length=160)
    expected_value = models.CharField(max_length=255, blank=True)
    result = models.CharField(max_length=20, choices=Result.choices, default=Result.PENDING)
    notes = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(fields=("inspection", "code"), name="quality_criterion_unique_code_inspection"),
        ]

    def save(self, *args, **kwargs):
        if self.inspection_id and self.inspection.status == QualityInspection.Status.COMPLETED:
            raise ValidationError("Criteria of a completed inspection are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.inspection.status == QualityInspection.Status.COMPLETED:
            raise ValidationError("Criteria of a completed inspection are immutable.")
        return super().delete(*args, **kwargs)


class QualityDefect(models.Model):
    class Severity(models.TextChoices):
        MINOR = "minor", "Minor"
        MAJOR = "major", "Major"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection = models.ForeignKey(QualityInspection, on_delete=models.CASCADE, related_name="defects")
    code = models.CharField(max_length=64, blank=True)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("1"), validators=[MinValueValidator(Decimal("0.0001"))])
    photo_references = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="quality_defect_quantity_positive"),
        ]

    def save(self, *args, **kwargs):
        if self.inspection_id and self.inspection.status == QualityInspection.Status.COMPLETED:
            raise ValidationError("Defects of a completed inspection are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.inspection.status == QualityInspection.Status.COMPLETED:
            raise ValidationError("Defects of a completed inspection are immutable.")
        return super().delete(*args, **kwargs)


class QualityRework(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="quality_reworks")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="quality_reworks")
    inspection = models.OneToOneField(QualityInspection, on_delete=models.PROTECT, related_name="rework")
    manufacturing_operation = models.ForeignKey(
        "manufacturing.ManufacturingOperation",
        on_delete=models.PROTECT,
        related_name="quality_reworks",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    instructions = models.TextField()
    result_notes = models.TextField(blank=True)
    created_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="created_quality_reworks")
    completed_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="completed_quality_reworks", null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the rework organization."})
        if self.inspection_id:
            if self.inspection.organization_id != self.organization_id or self.inspection.company_id != self.company_id:
                raise ValidationError({"inspection": "Inspection is outside the rework scope."})
            if self.inspection.status != QualityInspection.Status.COMPLETED or self.inspection.decision != QualityInspection.Decision.REWORK:
                raise ValidationError({"inspection": "Rework requires a completed inspection with rework decision."})
        if self.manufacturing_operation_id:
            if self.manufacturing_operation.organization_id != self.organization_id or self.manufacturing_operation.company_id != self.company_id:
                raise ValidationError({"manufacturing_operation": "Manufacturing operation is outside the rework scope."})
