from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ivadoo.audit.services import record_audit_event

from .models import ManufacturingOperation, ManufacturingOperationTransition, ManufacturingOrder


ZERO = Decimal("0")


def operation_snapshot(operation):
    return {
        "manufacturing_order_id": str(operation.manufacturing_order_id),
        "work_center_id": str(operation.work_center_id) if operation.work_center_id else None,
        "operation_type": operation.operation_type,
        "name": operation.name,
        "position": operation.position,
        "status": operation.status,
        "planned_minutes": operation.planned_minutes,
        "actual_minutes": operation.actual_minutes,
        "planned_quantity": str(operation.planned_quantity),
        "processed_quantity": str(operation.processed_quantity),
        "rework_count": operation.rework_count,
        "started_at": operation.started_at.isoformat() if operation.started_at else None,
        "completed_at": operation.completed_at.isoformat() if operation.completed_at else None,
    }


@transaction.atomic
def transition_operation(
    *,
    operation,
    action,
    actor,
    reason="",
    processed_quantity=None,
    actual_minutes=None,
    override_sequence=False,
    allow_sequence_override=False,
    request=None,
):
    operation = ManufacturingOperation.objects.select_for_update().get(pk=operation.pk)
    manufacturing_order = ManufacturingOrder.objects.select_for_update().get(
        pk=operation.manufacturing_order_id
    )
    if manufacturing_order.status != ManufacturingOrder.Status.IN_PROGRESS:
        raise ValidationError(
            "Manufacturing operations can execute only while the manufacturing order is in progress."
        )

    if override_sequence and not allow_sequence_override:
        raise ValidationError("Sequence override is not permitted in this scope.")
    if override_sequence and not reason.strip():
        raise ValidationError("Sequence override requires an explicit reason.")

    before = operation_snapshot(operation)
    from_status = operation.status
    now = timezone.now()

    if action == "start":
        if operation.status not in (
            ManufacturingOperation.Status.PENDING,
            ManufacturingOperation.Status.REWORK,
        ):
            raise ValidationError(
                f"Operation cannot start from status {operation.status}."
            )
        blockers = ManufacturingOperation.objects.filter(
            manufacturing_order_id=manufacturing_order.id,
            position__lt=operation.position,
        ).exclude(
            status__in=(
                ManufacturingOperation.Status.DONE,
                ManufacturingOperation.Status.CANCELLED,
            )
        )
        if blockers.exists() and not override_sequence:
            raise ValidationError(
                "Previous manufacturing operations must be completed before this operation starts."
            )
        operation.status = ManufacturingOperation.Status.IN_PROGRESS
        operation.started_at = now
        operation.completed_at = None
        update_fields = ["status", "started_at", "completed_at", "updated_at"]

    elif action == "complete":
        if operation.status != ManufacturingOperation.Status.IN_PROGRESS:
            raise ValidationError("Only an in-progress operation can be completed.")
        quantity = (
            Decimal(processed_quantity)
            if processed_quantity is not None
            else operation.processed_quantity
        )
        if quantity <= ZERO or quantity > operation.planned_quantity:
            raise ValidationError(
                "Processed quantity must be greater than zero and cannot exceed planned quantity."
            )
        if actual_minutes is not None:
            minutes = int(actual_minutes)
            if minutes < 0:
                raise ValidationError("Actual minutes cannot be negative.")
            operation.actual_minutes += minutes
        operation.processed_quantity = quantity
        operation.status = ManufacturingOperation.Status.DONE
        operation.completed_at = now
        update_fields = [
            "status",
            "processed_quantity",
            "actual_minutes",
            "completed_at",
            "updated_at",
        ]

    elif action == "rework":
        if operation.status != ManufacturingOperation.Status.DONE:
            raise ValidationError("Only a completed operation can be sent to rework.")
        if not reason.strip():
            raise ValidationError("Rework requires a reason.")
        operation.status = ManufacturingOperation.Status.REWORK
        operation.rework_count += 1
        operation.completed_at = None
        update_fields = ["status", "rework_count", "completed_at", "updated_at"]

    elif action == "cancel":
        if operation.status == ManufacturingOperation.Status.CANCELLED:
            return operation
        if operation.status == ManufacturingOperation.Status.DONE:
            raise ValidationError("Completed operations cannot be cancelled; use rework when needed.")
        if not reason.strip():
            raise ValidationError("Cancelling an operation requires a reason.")
        operation.status = ManufacturingOperation.Status.CANCELLED
        operation.completed_at = now
        update_fields = ["status", "completed_at", "updated_at"]

    else:
        raise ValidationError("Unsupported manufacturing operation action.")

    operation.full_clean()
    operation.save(update_fields=tuple(dict.fromkeys(update_fields)))
    ManufacturingOperationTransition.objects.create(
        operation=operation,
        from_status=from_status,
        to_status=operation.status,
        action=action,
        reason=reason,
        sequence_override=bool(override_sequence),
        processed_quantity=operation.processed_quantity,
        actual_minutes=operation.actual_minutes,
        actor=actor,
    )
    record_audit_event(
        organization=operation.organization,
        actor=actor,
        action=f"manufacturing.operation.{action}",
        object_instance=operation,
        before=before,
        after=operation_snapshot(operation),
        company_id=operation.company_id,
        request=request,
        metadata={"sequence_override": bool(override_sequence), "reason": reason},
    )
    return operation
