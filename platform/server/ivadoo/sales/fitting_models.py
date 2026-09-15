import uuid

from django.core.exceptions import ValidationError
from django.db import models


class FittingSession(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Result(models.TextChoices):
        PENDING = "pending", "Pending"
        FIT_OK = "fit_ok", "Fit accepted"
        ALTERATION_REQUIRED = "alteration_required", "Alteration required"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="fitting_sessions")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="fitting_sessions")
    order = models.ForeignKey("sales.Order", on_delete=models.PROTECT, related_name="fitting_sessions")
    scheduled_at = models.DateTimeField()
    performed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    result = models.CharField(max_length=24, choices=Result.choices, default=Result.PENDING)
    requires_customer_validation = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="created_fitting_sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-scheduled_at", "-created_at")

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the fitting organization."})
        if self.order_id:
            if self.order.organization_id != self.organization_id or self.order.company_id != self.company_id:
                raise ValidationError({"order": "Order is outside the fitting scope."})
            if self._state.adding and self.order.status != self.order.Status.CONFIRMED:
                raise ValidationError({"order": "Fittings can be created only for confirmed orders."})


class AlterationRequest(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="alteration_requests")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="alteration_requests")
    order = models.ForeignKey("sales.Order", on_delete=models.PROTECT, related_name="alteration_requests")
    fitting = models.ForeignKey(FittingSession, on_delete=models.PROTECT, related_name="alterations")
    order_line = models.ForeignKey("sales.OrderLine", on_delete=models.PROTECT, related_name="alteration_requests", null=True, blank=True)
    quality_defect = models.ForeignKey("quality.QualityDefect", on_delete=models.PROTECT, related_name="alteration_requests", null=True, blank=True)
    manufacturing_order = models.ForeignKey("manufacturing.ManufacturingOrder", on_delete=models.PROTECT, related_name="alteration_requests", null=True, blank=True)
    manufacturing_operation = models.ForeignKey("manufacturing.ManufacturingOperation", on_delete=models.PROTECT, related_name="alteration_requests", null=True, blank=True)
    reason = models.TextField()
    adjustment_notes = models.TextField(blank=True)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="created_alteration_requests")
    completed_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="completed_alteration_requests", null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the alteration organization."})
        if self.order_id and (self.order.organization_id != self.organization_id or self.order.company_id != self.company_id):
            raise ValidationError({"order": "Order is outside the alteration scope."})
        if self.fitting_id and self.fitting.order_id != self.order_id:
            raise ValidationError({"fitting": "Fitting must belong to the alteration order."})
        if self.order_line_id and self.order_line.order_id != self.order_id:
            raise ValidationError({"order_line": "Order line must belong to the alteration order."})
        if self.quality_defect_id:
            inspection = self.quality_defect.inspection
            if inspection.organization_id != self.organization_id or inspection.company_id != self.company_id:
                raise ValidationError({"quality_defect": "Quality defect is outside the alteration scope."})
        if self.manufacturing_order_id:
            mo = self.manufacturing_order
            if mo.organization_id != self.organization_id or mo.company_id != self.company_id or mo.order_id != self.order_id:
                raise ValidationError({"manufacturing_order": "Manufacturing order must be linked to the alteration sales order."})
        if self.manufacturing_operation_id:
            operation = self.manufacturing_operation
            if operation.organization_id != self.organization_id or operation.company_id != self.company_id:
                raise ValidationError({"manufacturing_operation": "Manufacturing operation is outside the alteration scope."})
            if operation.manufacturing_order.order_id != self.order_id:
                raise ValidationError({"manufacturing_operation": "Manufacturing operation must belong to the alteration sales order."})
            if self.manufacturing_order_id and operation.manufacturing_order_id != self.manufacturing_order_id:
                raise ValidationError({"manufacturing_operation": "Manufacturing operation must belong to the selected manufacturing order."})


class CustomerValidation(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="customer_validations")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="customer_validations")
    order = models.ForeignKey("sales.Order", on_delete=models.PROTECT, related_name="customer_validations")
    fitting = models.OneToOneField(FittingSession, on_delete=models.PROTECT, related_name="customer_validation")
    decision = models.CharField(max_length=16, choices=Decision.choices)
    customer_name = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    evidence_reference = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="recorded_customer_validations")
    validated_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-validated_at", "-created_at")

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the customer validation organization."})
        if self.order_id and (self.order.organization_id != self.organization_id or self.order.company_id != self.company_id):
            raise ValidationError({"order": "Order is outside the customer validation scope."})
        if self.fitting_id:
            if self.fitting.order_id != self.order_id:
                raise ValidationError({"fitting": "Fitting must belong to the customer validation order."})
            if self.fitting.status != FittingSession.Status.COMPLETED or self.fitting.result != FittingSession.Result.FIT_OK:
                raise ValidationError({"fitting": "Customer validation requires a completed fitting with an accepted fit result."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Customer validation records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Customer validation records are immutable.")
