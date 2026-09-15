import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class ApprovalRule(models.Model):
    class Resource(models.TextChoices):
        PURCHASE_ORDER = "purchase_order", "Purchase order"
        STOCK_MOVEMENT = "stock_movement", "Stock movement"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="operational_approval_rules")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="operational_approval_rules", null=True, blank=True)
    establishment = models.ForeignKey("organizations.Establishment", on_delete=models.PROTECT, related_name="operational_approval_rules", null=True, blank=True)
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT, related_name="operational_approval_rules", null=True, blank=True)
    resource = models.CharField(max_length=32, choices=Resource.choices)
    action = models.CharField(max_length=64)
    threshold = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    require_distinct_approver = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("resource", "action", "-threshold")
        constraints = [
            models.CheckConstraint(condition=models.Q(threshold__gte=0), name="operations_approval_threshold_nonnegative"),
            models.UniqueConstraint(
                fields=("organization", "company", "establishment", "warehouse", "resource", "action", "threshold"),
                name="operations_unique_approval_rule_scope",
                nulls_distinct=False,
            ),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the approval rule organization."})
        if self.establishment_id:
            if not self.company_id or self.establishment.company_id != self.company_id:
                raise ValidationError({"establishment": "Establishment must belong to the selected company."})
        if self.warehouse_id:
            if not self.company_id or self.warehouse.company_id != self.company_id:
                raise ValidationError({"warehouse": "Warehouse must belong to the selected company."})
            if self.establishment_id and self.warehouse.establishment_id != self.establishment_id:
                raise ValidationError({"warehouse": "Warehouse must belong to the selected establishment."})


class StockMovementApproval(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="stock_movement_approvals")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="stock_movement_approvals")
    establishment = models.ForeignKey("organizations.Establishment", on_delete=models.PROTECT, related_name="stock_movement_approvals", null=True, blank=True)
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT, related_name="stock_movement_approvals")
    movement_type = models.CharField(max_length=32)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    payload = models.JSONField(default=dict)
    payload_digest = models.CharField(max_length=64)
    idempotency_key = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="requested_stock_movement_approvals")
    decided_by = models.ForeignKey("identity.User", on_delete=models.PROTECT, related_name="decided_stock_movement_approvals", null=True, blank=True)
    decision_reason = models.CharField(max_length=255, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_movement_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="operations_stock_approval_quantity_positive"),
            models.UniqueConstraint(
                fields=("organization", "idempotency_key"),
                condition=~models.Q(idempotency_key=""),
                name="operations_stock_approval_unique_idempotency_org",
            ),
        ]

    def clean(self):
        super().clean()
        if self.company.organization_id != self.organization_id:
            raise ValidationError({"company": "Company is outside the approval organization."})
        if self.warehouse.organization_id != self.organization_id or self.warehouse.company_id != self.company_id:
            raise ValidationError({"warehouse": "Warehouse is outside the approval scope."})
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError({"establishment": "Establishment must belong to the selected company."})
