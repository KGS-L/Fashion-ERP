import hashlib
import json
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    CommissionCalculation,
    CommissionRule,
    EmployeeTask,
    EmployeeTimeEntry,
    ProductivitySnapshot,
)


RATE_QUANTUM = Decimal("0.0001")
BASIS_QUANTUM = Decimal("0.000001")


def _period_bounds(period_start, period_end, site=None):
    if period_end < period_start:
        raise ValidationError({"period_end": "Period end cannot precede period start."})
    zone = ZoneInfo(getattr(site, "timezone", None) or "UTC")
    local_start = datetime.combine(period_start, time.min, tzinfo=zone)
    local_end = datetime.combine(period_end + timedelta(days=1), time.min, tzinfo=zone)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc), zone.key


def _scope_tasks(queryset, *, company, establishment=None, workshop=None):
    queryset = queryset.filter(company=company)
    if workshop:
        return queryset.filter(workshop=workshop)
    if establishment:
        return queryset.filter(establishment=establishment)
    return queryset


def _scope_time_entries(queryset, *, company, establishment=None, workshop=None):
    queryset = queryset.filter(company=company)
    if workshop:
        return queryset.filter(workshop=workshop)
    if establishment:
        return queryset.filter(establishment=establishment)
    return queryset


def _canonical_fingerprint(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _overlap_minutes(entry, period_start_at, period_end_at):
    if not entry.ended_at:
        return 0
    start = max(entry.started_at, period_start_at)
    end = min(entry.ended_at, period_end_at)
    if end <= start:
        return 0
    return int((end - start).total_seconds() // 60)


def _closed_time_entries(*, employee, company, establishment, workshop, start_at, end_at):
    entries = _scope_time_entries(
        EmployeeTimeEntry.objects.filter(
            employee=employee,
            ended_at__isnull=False,
            started_at__lt=end_at,
            ended_at__gt=start_at,
        ).select_related("task"),
        company=company,
        establishment=establishment,
        workshop=workshop,
    )
    return list(entries.order_by("started_at", "id"))


def generate_productivity_snapshot(
    *,
    employee,
    company,
    period_start,
    period_end,
    generated_by,
    establishment=None,
    workshop=None,
):
    if employee.organization_id != company.organization_id:
        raise ValidationError({"employee_id": "Employee is outside the selected company organization."})
    if employee.company_id != company.id:
        raise ValidationError({"employee_id": "Employee must belong to the selected company."})
    if establishment and establishment.company_id != company.id:
        raise ValidationError({"establishment_id": "Establishment must belong to the selected company."})
    if workshop:
        if workshop.company_id != company.id:
            raise ValidationError({"workshop_id": "Workshop must belong to the selected company."})
        if workshop.site_type not in {"workshop", "mixed"}:
            raise ValidationError({"workshop_id": "Workshop must use the workshop or mixed site type."})

    site = workshop or establishment
    start_at, end_at, timezone_name = _period_bounds(period_start, period_end, site)

    task_queryset = _scope_tasks(
        EmployeeTask.objects.filter(employee=employee)
        .exclude(status=EmployeeTask.Status.CANCELLED)
        .select_related("manufacturing_operation"),
        company=company,
        establishment=establishment,
        workshop=workshop,
    )
    assigned_tasks = list(
        task_queryset.filter(
            Q(planned_start__gte=start_at, planned_start__lt=end_at)
            | Q(
                planned_start__isnull=True,
                created_at__gte=start_at,
                created_at__lt=end_at,
            )
        ).order_by("created_at", "id")
    )
    completed_tasks = [
        task
        for task in assigned_tasks
        if task.status == EmployeeTask.Status.DONE
        and task.completed_at
        and start_at <= task.completed_at < end_at
    ]

    time_entries = _closed_time_entries(
        employee=employee,
        company=company,
        establishment=establishment,
        workshop=workshop,
        start_at=start_at,
        end_at=end_at,
    )
    tracked_minutes = sum(
        _overlap_minutes(entry, start_at, end_at) for entry in time_entries
    )

    operations = {}
    for task in assigned_tasks:
        operation = task.manufacturing_operation
        if operation:
            operations[str(operation.id)] = operation

    quantity_rates = []
    for operation in operations.values():
        if operation.planned_quantity and operation.planned_quantity > 0:
            quantity_rates.append(
                (operation.processed_quantity / operation.planned_quantity) * Decimal("100")
            )

    assigned_count = len(assigned_tasks)
    completed_count = len(completed_tasks)
    task_completion_rate = (
        (Decimal(completed_count) / Decimal(assigned_count)) * Decimal("100")
        if assigned_count
        else Decimal("0")
    ).quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)
    quantity_completion_rate = (
        sum(quantity_rates, Decimal("0")) / Decimal(len(quantity_rates))
        if quantity_rates
        else Decimal("0")
    ).quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)

    source_payload = {
        "formula_version": ProductivitySnapshot.FORMULA_VERSION,
        "employee_id": str(employee.id),
        "company_id": str(company.id),
        "establishment_id": str(establishment.id) if establishment else None,
        "workshop_id": str(workshop.id) if workshop else None,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "timezone": timezone_name,
        "tasks": [
            {
                "id": str(task.id),
                "status": task.status,
                "planned_start": task.planned_start.isoformat() if task.planned_start else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "updated_at": task.updated_at.isoformat(),
                "operation_id": (
                    str(task.manufacturing_operation_id)
                    if task.manufacturing_operation_id
                    else None
                ),
            }
            for task in assigned_tasks
        ],
        "time_entries": [
            {
                "id": str(entry.id),
                "started_at": entry.started_at.isoformat(),
                "ended_at": entry.ended_at.isoformat() if entry.ended_at else None,
                "duration_minutes": entry.duration_minutes,
                "updated_at": entry.updated_at.isoformat(),
            }
            for entry in time_entries
        ],
        "operations": [
            {
                "id": str(operation.id),
                "planned_quantity": str(operation.planned_quantity),
                "processed_quantity": str(operation.processed_quantity),
                "updated_at": operation.updated_at.isoformat(),
            }
            for operation in sorted(operations.values(), key=lambda item: str(item.id))
        ],
    }
    fingerprint = _canonical_fingerprint(source_payload)

    with transaction.atomic():
        snapshot, _ = ProductivitySnapshot.objects.get_or_create(
            employee=employee,
            company=company,
            establishment=establishment,
            workshop=workshop,
            period_start=period_start,
            period_end=period_end,
            formula_version=ProductivitySnapshot.FORMULA_VERSION,
            source_fingerprint=fingerprint,
            defaults={
                "assigned_tasks": assigned_count,
                "completed_tasks": completed_count,
                "task_completion_rate": task_completion_rate,
                "tracked_minutes": tracked_minutes,
                "linked_operation_count": len(operations),
                "quantity_completion_rate": quantity_completion_rate,
                "source_summary": source_payload,
                "generated_by": generated_by,
            },
        )
    return snapshot


def _validate_rule_period(rule, period_start, period_end):
    if period_end < period_start:
        raise ValidationError({"period_end": "Period end cannot precede period start."})
    if not rule.is_active:
        raise ValidationError({"rule_id": "Commission rule is inactive."})
    if rule.active_from and period_end < rule.active_from:
        raise ValidationError({"period_start": "Period is before the commission rule activation."})
    if rule.active_until and period_start > rule.active_until:
        raise ValidationError({"period_end": "Period is after the commission rule expiration."})


def calculate_commission(*, rule, employee, period_start, period_end, generated_by):
    _validate_rule_period(rule, period_start, period_end)
    if employee.organization_id != rule.organization_id or employee.company_id != rule.company_id:
        raise ValidationError({"employee_id": "Employee is outside the commission rule scope."})
    if rule.employee_id and rule.employee_id != employee.id:
        raise ValidationError({"employee_id": "Commission rule is assigned to another employee."})

    company = rule.company
    establishment = rule.establishment
    workshop = rule.workshop
    site = workshop or establishment
    start_at, end_at, timezone_name = _period_bounds(period_start, period_end, site)

    source_rows = []
    if rule.basis == CommissionRule.Basis.COMPLETED_TASK:
        tasks = _scope_tasks(
            EmployeeTask.objects.filter(
                employee=employee,
                status=EmployeeTask.Status.DONE,
                completed_at__gte=start_at,
                completed_at__lt=end_at,
            ),
            company=company,
            establishment=establishment,
            workshop=workshop,
        ).order_by("completed_at", "id")
        tasks = list(tasks)
        basis_quantity = Decimal(len(tasks)).quantize(BASIS_QUANTUM)
        source_rows = [
            {
                "id": str(task.id),
                "completed_at": task.completed_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
            }
            for task in tasks
        ]
        source_summary = {"completed_task_count": len(tasks)}
    elif rule.basis == CommissionRule.Basis.TRACKED_HOUR:
        entries = _closed_time_entries(
            employee=employee,
            company=company,
            establishment=establishment,
            workshop=workshop,
            start_at=start_at,
            end_at=end_at,
        )
        minutes = sum(_overlap_minutes(entry, start_at, end_at) for entry in entries)
        basis_quantity = (Decimal(minutes) / Decimal("60")).quantize(
            BASIS_QUANTUM, rounding=ROUND_HALF_UP
        )
        source_rows = [
            {
                "id": str(entry.id),
                "started_at": entry.started_at.isoformat(),
                "ended_at": entry.ended_at.isoformat() if entry.ended_at else None,
                "updated_at": entry.updated_at.isoformat(),
            }
            for entry in entries
        ]
        source_summary = {"tracked_minutes": minutes, "tracked_hours": str(basis_quantity)}
    else:
        raise ValidationError({"rule_id": "Unsupported commission basis."})

    currency_quantum = Decimal("1").scaleb(-rule.currency.decimal_places)
    amount = (basis_quantity * rule.rate).quantize(
        currency_quantum,
        rounding=ROUND_HALF_UP,
    )
    source_payload = {
        "formula_version": CommissionCalculation.FORMULA_VERSION,
        "rule_id": str(rule.id),
        "rule_updated_at": rule.updated_at.isoformat(),
        "employee_id": str(employee.id),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "timezone": timezone_name,
        "basis": rule.basis,
        "rows": source_rows,
    }
    fingerprint = _canonical_fingerprint(source_payload)
    rule_snapshot = {
        "code": rule.code,
        "name": rule.name,
        "basis": rule.basis,
        "rate": str(rule.rate),
        "currency": rule.currency_id,
        "company_id": str(rule.company_id),
        "establishment_id": str(rule.establishment_id) if rule.establishment_id else None,
        "workshop_id": str(rule.workshop_id) if rule.workshop_id else None,
        "employee_id": str(rule.employee_id) if rule.employee_id else None,
        "active_from": rule.active_from.isoformat() if rule.active_from else None,
        "active_until": rule.active_until.isoformat() if rule.active_until else None,
    }
    source_summary.update({"timezone": timezone_name, "source_rows": source_rows})

    with transaction.atomic():
        calculation, _ = CommissionCalculation.objects.get_or_create(
            rule=rule,
            employee=employee,
            period_start=period_start,
            period_end=period_end,
            formula_version=CommissionCalculation.FORMULA_VERSION,
            source_fingerprint=fingerprint,
            defaults={
                "company": company,
                "establishment": establishment,
                "workshop": workshop,
                "basis_quantity": basis_quantity,
                "rate_snapshot": rule.rate,
                "amount": amount,
                "currency": rule.currency,
                "rule_snapshot": rule_snapshot,
                "source_summary": source_summary,
                "generated_by": generated_by,
            },
        )
    return calculation
