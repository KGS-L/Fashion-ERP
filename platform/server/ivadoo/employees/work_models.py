import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from .models import Employee


def validate_employee_scope(*, employee, company, establishment=None, workshop=None):
    if employee and company and employee.organization_id != company.organization_id:
        raise ValidationError(
            {"company": "Company must belong to the employee organization."}
        )
    if establishment and company and establishment.company_id != company.id:
        raise ValidationError(
            {"establishment": "Establishment must belong to the selected company."}
        )
    if workshop:
        if company and workshop.company_id != company.id:
            raise ValidationError({"workshop": "Workshop must belong to the selected company."})
        if workshop.site_type not in {"workshop", "mixed"}:
            raise ValidationError(
                {"workshop": "Workshop must use the workshop or mixed establishment type."}
            )


class EmployeeSchedule(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="schedules",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="employee_schedules",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_schedules",
        null=True,
        blank=True,
    )
    workshop = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_workshop_schedules",
        null=True,
        blank=True,
        limit_choices_to={"site_type__in": ("workshop", "mixed")},
    )
    label = models.CharField(max_length=160, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_employee_schedules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("starts_at", "employee_id")
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="employee_schedule_end_after_start",
            )
        ]

    def clean(self):
        super().clean()
        validate_employee_scope(
            employee=self.employee if self.employee_id else None,
            company=self.company if self.company_id else None,
            establishment=self.establishment if self.establishment_id else None,
            workshop=self.workshop if self.workshop_id else None,
        )
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Schedule end must be after its start."})


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        LATE = "late", "Late"
        ABSENT = "absent", "Absent"
        EXCUSED = "excused", "Excused"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    schedule = models.ForeignKey(
        EmployeeSchedule,
        on_delete=models.PROTECT,
        related_name="attendance_records",
        null=True,
        blank=True,
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="employee_attendance_records",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_attendance_records",
        null=True,
        blank=True,
    )
    workshop = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_workshop_attendance_records",
        null=True,
        blank=True,
        limit_choices_to={"site_type__in": ("workshop", "mixed")},
    )
    attendance_date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices)
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="recorded_employee_attendance",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-attendance_date", "employee_id", "check_in_at")
        constraints = [
            models.CheckConstraint(
                condition=(Q(check_out_at__isnull=True) | Q(check_out_at__gte=F("check_in_at"))),
                name="employee_attendance_checkout_after_checkin",
            )
        ]

    def clean(self):
        super().clean()
        validate_employee_scope(
            employee=self.employee if self.employee_id else None,
            company=self.company if self.company_id else None,
            establishment=self.establishment if self.establishment_id else None,
            workshop=self.workshop if self.workshop_id else None,
        )
        if self.schedule_id:
            if self.schedule.employee_id != self.employee_id:
                raise ValidationError({"schedule": "Schedule must belong to the selected employee."})
            if self.schedule.company_id != self.company_id:
                raise ValidationError({"schedule": "Schedule must belong to the selected company."})
        if self.check_in_at and self.check_out_at and self.check_out_at < self.check_in_at:
            raise ValidationError({"check_out_at": "Check-out cannot precede check-in."})


class EmployeeTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In progress"
        BLOCKED = "blocked", "Blocked"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="employee_tasks",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_tasks",
        null=True,
        blank=True,
    )
    workshop = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_workshop_tasks",
        null=True,
        blank=True,
        limit_choices_to={"site_type__in": ("workshop", "mixed")},
    )
    order = models.ForeignKey(
        "sales.Order",
        on_delete=models.PROTECT,
        related_name="employee_tasks",
        null=True,
        blank=True,
    )
    manufacturing_operation = models.ForeignKey(
        "manufacturing.ManufacturingOperation",
        on_delete=models.PROTECT,
        related_name="employee_tasks",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    planned_start = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_employee_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-priority", "due_at", "created_at")

    def clean(self):
        super().clean()
        validate_employee_scope(
            employee=self.employee if self.employee_id else None,
            company=self.company if self.company_id else None,
            establishment=self.establishment if self.establishment_id else None,
            workshop=self.workshop if self.workshop_id else None,
        )
        organization_id = self.employee.organization_id if self.employee_id else None
        if self.order_id:
            if self.order.organization_id != organization_id or self.order.company_id != self.company_id:
                raise ValidationError({"order": "Order must belong to the task organization and company."})
        if self.manufacturing_operation_id:
            operation = self.manufacturing_operation
            if operation.organization_id != organization_id or operation.company_id != self.company_id:
                raise ValidationError(
                    {"manufacturing_operation": "Operation must belong to the task organization and company."}
                )
            source_order_id = operation.manufacturing_order.order_id
            if self.order_id and source_order_id and source_order_id != self.order_id:
                raise ValidationError(
                    {"order": "Order must match the manufacturing operation source order."}
                )
        if self.planned_start and self.due_at and self.due_at < self.planned_start:
            raise ValidationError({"due_at": "Due date cannot precede planned start."})
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValidationError({"completed_at": "Completion cannot precede task start."})


class EmployeeTaskTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        EmployeeTask,
        on_delete=models.PROTECT,
        related_name="history",
    )
    from_status = models.CharField(max_length=16)
    to_status = models.CharField(max_length=16)
    note = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="employee_task_transitions",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("occurred_at", "id")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Employee task transition history is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Employee task transition history is immutable.")


class EmployeeTimeEntry(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        TIMER = "timer", "Timer"
        MOBILE = "mobile", "Mobile"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="time_entries",
    )
    task = models.ForeignKey(
        EmployeeTask,
        on_delete=models.PROTECT,
        related_name="time_entries",
        null=True,
        blank=True,
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="employee_time_entries",
    )
    establishment = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_time_entries",
        null=True,
        blank=True,
    )
    workshop = models.ForeignKey(
        "organizations.Establishment",
        on_delete=models.PROTECT,
        related_name="employee_workshop_time_entries",
        null=True,
        blank=True,
        limit_choices_to={"site_type__in": ("workshop", "mixed")},
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=0, editable=False)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="recorded_employee_time_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-started_at", "employee_id")
        constraints = [
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("started_at")),
                name="employee_time_end_after_start",
            )
        ]

    def clean(self):
        super().clean()
        validate_employee_scope(
            employee=self.employee if self.employee_id else None,
            company=self.company if self.company_id else None,
            establishment=self.establishment if self.establishment_id else None,
            workshop=self.workshop if self.workshop_id else None,
        )
        if self.task_id:
            if self.task.employee_id != self.employee_id:
                raise ValidationError({"task": "Time entry task must belong to the employee."})
            if self.task.company_id != self.company_id:
                raise ValidationError({"task": "Time entry task must belong to the selected company."})
        if self.ended_at and self.ended_at < self.started_at:
            raise ValidationError({"ended_at": "End cannot precede start."})
