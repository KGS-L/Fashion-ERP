import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from .models import Employee


class ProductivitySnapshot(models.Model):
    FORMULA_VERSION = "v1"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="productivity_snapshots",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="employee_productivity_snapshots",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_productivity_snapshots",
        null=True,
        blank=True,
    )
    workshop = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_workshop_productivity_snapshots",
        null=True,
        blank=True,
        limit_choices_to={"site_type__in": ("workshop", "mixed")},
    )
    period_start = models.DateField()
    period_end = models.DateField()
    assigned_tasks = models.PositiveIntegerField(default=0)
    completed_tasks = models.PositiveIntegerField(default=0)
    task_completion_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=Decimal("0"),
    )
    tracked_minutes = models.PositiveIntegerField(default=0)
    linked_operation_count = models.PositiveIntegerField(default=0)
    quantity_completion_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=Decimal("0"),
    )
    formula_version = models.CharField(max_length=16, default=FORMULA_VERSION)
    source_fingerprint = models.CharField(max_length=64)
    source_summary = models.JSONField(default=dict)
    generated_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="generated_productivity_snapshots",
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-period_end", "employee__display_name", "-generated_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start")),
                name="employee_productivity_period_valid",
            ),
            models.CheckConstraint(
                condition=Q(completed_tasks__lte=F("assigned_tasks")),
                name="employee_productivity_completed_lte_assigned",
            ),
            models.UniqueConstraint(
                fields=(
                    "employee",
                    "company",
                    "establishment",
                    "workshop",
                    "period_start",
                    "period_end",
                    "formula_version",
                    "source_fingerprint",
                ),
                name="employee_productivity_snapshot_source_unique",
                nulls_distinct=False,
            ),
        ]

    def clean(self):
        super().clean()
        organization_id = self.employee.organization_id if self.employee_id else None
        if self.company_id and self.company.organization_id != organization_id:
            raise ValidationError(
                {"company": "Productivity company must belong to the employee organization."}
            )
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError(
                {"establishment": "Productivity establishment must belong to the company."}
            )
        if self.workshop_id:
            if self.workshop.company_id != self.company_id:
                raise ValidationError(
                    {"workshop": "Productivity workshop must belong to the company."}
                )
            if self.workshop.site_type not in {"workshop", "mixed"}:
                raise ValidationError(
                    {"workshop": "Workshop must use the workshop or mixed establishment type."}
                )
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": "Period end cannot precede period start."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Productivity snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Productivity snapshots are immutable.")


class CommissionRule(models.Model):
    class Basis(models.TextChoices):
        COMPLETED_TASK = "completed_task", "Completed task"
        TRACKED_HOUR = "tracked_hour", "Tracked hour"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="employee_commission_rules",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="employee_commission_rules",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_commission_rules",
        null=True,
        blank=True,
    )
    workshop = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_workshop_commission_rules",
        null=True,
        blank=True,
        limit_choices_to={"site_type__in": ("workshop", "mixed")},
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="commission_rules",
        null=True,
        blank=True,
    )
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    basis = models.CharField(max_length=24, choices=Basis.choices)
    rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.ForeignKey(
        "internationalization.Currency",
        on_delete=models.PROTECT,
        related_name="employee_commission_rules",
    )
    active_from = models.DateField(null=True, blank=True)
    active_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_employee_commission_rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("company__name", "code")
        constraints = [
            models.UniqueConstraint(
                fields=("company", "code"),
                name="employee_commission_rule_code_company_unique",
            ),
            models.CheckConstraint(
                condition=Q(rate__gte=0),
                name="employee_commission_rule_rate_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(active_until__isnull=True)
                    | Q(active_from__isnull=True)
                    | Q(active_until__gte=F("active_from"))
                ),
                name="employee_commission_rule_period_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.company_id and self.company.organization_id != self.organization_id:
            raise ValidationError(
                {"company": "Commission company must belong to the rule organization."}
            )
        if self.establishment_id and self.establishment.company_id != self.company_id:
            raise ValidationError(
                {"establishment": "Commission establishment must belong to the company."}
            )
        if self.workshop_id:
            if self.workshop.company_id != self.company_id:
                raise ValidationError({"workshop": "Commission workshop must belong to the company."})
            if self.workshop.site_type not in {"workshop", "mixed"}:
                raise ValidationError(
                    {"workshop": "Workshop must use the workshop or mixed establishment type."}
                )
        if self.employee_id:
            if self.employee.organization_id != self.organization_id:
                raise ValidationError(
                    {"employee": "Commission employee must belong to the rule organization."}
                )
            if self.employee.company_id != self.company_id:
                raise ValidationError(
                    {"employee": "Commission employee must belong to the rule company."}
                )
        if self.active_from and self.active_until and self.active_until < self.active_from:
            raise ValidationError(
                {"active_until": "Active until cannot precede active from."}
            )


class CommissionCalculation(models.Model):
    FORMULA_VERSION = "v1"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(
        CommissionRule,
        on_delete=models.PROTECT,
        related_name="calculations",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="commission_calculations",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="employee_commission_calculations",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_commission_calculations",
        null=True,
        blank=True,
    )
    workshop = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_workshop_commission_calculations",
        null=True,
        blank=True,
        limit_choices_to={"site_type__in": ("workshop", "mixed")},
    )
    period_start = models.DateField()
    period_end = models.DateField()
    basis_quantity = models.DecimalField(max_digits=18, decimal_places=6)
    rate_snapshot = models.DecimalField(max_digits=18, decimal_places=6)
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.ForeignKey(
        "internationalization.Currency",
        on_delete=models.PROTECT,
        related_name="employee_commission_calculations",
    )
    formula_version = models.CharField(max_length=16, default=FORMULA_VERSION)
    source_fingerprint = models.CharField(max_length=64)
    rule_snapshot = models.JSONField(default=dict)
    source_summary = models.JSONField(default=dict)
    generated_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="generated_employee_commissions",
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-period_end", "employee__display_name", "-generated_at")
        constraints = [
            models.CheckConstraint(
                condition=Q(period_end__gte=F("period_start")),
                name="employee_commission_calculation_period_valid",
            ),
            models.CheckConstraint(
                condition=Q(basis_quantity__gte=0),
                name="employee_commission_basis_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(rate_snapshot__gte=0),
                name="employee_commission_rate_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=0),
                name="employee_commission_amount_nonnegative",
            ),
            models.UniqueConstraint(
                fields=(
                    "rule",
                    "employee",
                    "period_start",
                    "period_end",
                    "formula_version",
                    "source_fingerprint",
                ),
                name="employee_commission_calculation_source_unique",
            ),
        ]

    def clean(self):
        super().clean()
        organization_id = self.employee.organization_id if self.employee_id else None
        if self.company_id and self.company.organization_id != organization_id:
            raise ValidationError(
                {"company": "Commission calculation company must belong to the employee organization."}
            )
        if self.rule_id:
            if self.rule.organization_id != organization_id:
                raise ValidationError(
                    {"rule": "Commission rule must belong to the employee organization."}
                )
            if self.rule.company_id != self.company_id:
                raise ValidationError(
                    {"rule": "Commission rule must belong to the calculation company."}
                )
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": "Period end cannot precede period start."})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Commission calculations are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Commission calculations are immutable.")
