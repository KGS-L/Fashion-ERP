from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ivadoo.audit.services import audit_snapshot, record_audit_event
from ivadoo.manufacturing.models import ManufacturingOperation
from ivadoo.manufacturing.operation_services import transition_operation

from .models import AlterationRequest, CustomerValidation, FittingSession


def fitting_snapshot(fitting):
    return {
        "order_id": str(fitting.order_id),
        "scheduled_at": fitting.scheduled_at.isoformat(),
        "performed_at": fitting.performed_at.isoformat() if fitting.performed_at else None,
        "status": fitting.status,
        "result": fitting.result,
        "requires_customer_validation": fitting.requires_customer_validation,
    }


@transaction.atomic
def transition_fitting(*, fitting, action, actor, result=None, notes=None, request=None):
    fitting = FittingSession.objects.select_for_update().get(pk=fitting.pk)
    before = fitting_snapshot(fitting)
    if action == "complete":
        if fitting.status != FittingSession.Status.SCHEDULED:
            raise ValidationError("Only a scheduled fitting can be completed.")
        if result not in (FittingSession.Result.FIT_OK, FittingSession.Result.ALTERATION_REQUIRED):
            raise ValidationError("A fitting completion requires fit_ok or alteration_required result.")
        fitting.status = FittingSession.Status.COMPLETED
        fitting.result = result
        fitting.performed_at = timezone.now()
        if notes is not None:
            fitting.notes = notes
        fitting.save(update_fields=("status", "result", "performed_at", "notes", "updated_at"))
    elif action == "cancel":
        if fitting.status == FittingSession.Status.CANCELLED:
            return fitting
        if fitting.status == FittingSession.Status.COMPLETED:
            raise ValidationError("Completed fittings cannot be cancelled.")
        fitting.status = FittingSession.Status.CANCELLED
        fitting.save(update_fields=("status", "updated_at"))
    else:
        raise ValidationError("Unsupported fitting action.")
    record_audit_event(
        organization=fitting.organization,
        actor=actor,
        action=f"fashion.fitting.{action}",
        object_instance=fitting,
        before=before,
        after=fitting_snapshot(fitting),
        company_id=fitting.company_id,
        request=request,
    )
    return fitting


@transaction.atomic
def transition_alteration(
    *, alteration, action, actor, reopen_operation=False, allow_operation_rework=False, request=None
):
    alteration = AlterationRequest.objects.select_for_update().get(pk=alteration.pk)
    if action == "start":
        if alteration.status != AlterationRequest.Status.OPEN:
            raise ValidationError("Only an open alteration can be started.")
        if reopen_operation:
            if not alteration.manufacturing_operation_id:
                raise ValidationError("No manufacturing operation is linked to this alteration.")
            if not allow_operation_rework:
                raise ValidationError("Manufacturing operation rework is not permitted in this scope.")
            operation = ManufacturingOperation.objects.get(pk=alteration.manufacturing_operation_id)
            if operation.status == ManufacturingOperation.Status.DONE:
                transition_operation(
                    operation=operation,
                    action="rework",
                    actor=actor,
                    reason=f"Customer alteration: {alteration.reason}",
                    request=request,
                )
            elif operation.status != ManufacturingOperation.Status.REWORK:
                raise ValidationError("Linked manufacturing operation must be done or already in rework before reopening.")
        before = audit_snapshot(alteration)
        alteration.status = AlterationRequest.Status.IN_PROGRESS
        alteration.started_at = timezone.now()
        alteration.save(update_fields=("status", "started_at", "updated_at"))
    elif action == "complete":
        if alteration.status != AlterationRequest.Status.IN_PROGRESS:
            raise ValidationError("Only an in-progress alteration can be completed.")
        before = audit_snapshot(alteration)
        alteration.status = AlterationRequest.Status.DONE
        alteration.completed_by = actor
        alteration.completed_at = timezone.now()
        alteration.save(update_fields=("status", "completed_by", "completed_at", "updated_at"))
    elif action == "cancel":
        if alteration.status == AlterationRequest.Status.CANCELLED:
            return alteration
        if alteration.status == AlterationRequest.Status.DONE:
            raise ValidationError("Completed alterations cannot be cancelled.")
        before = audit_snapshot(alteration)
        alteration.status = AlterationRequest.Status.CANCELLED
        alteration.completed_by = actor
        alteration.completed_at = timezone.now()
        alteration.save(update_fields=("status", "completed_by", "completed_at", "updated_at"))
    else:
        raise ValidationError("Unsupported alteration action.")
    record_audit_event(
        organization=alteration.organization,
        actor=actor,
        action=f"fashion.alteration.{action}",
        object_instance=alteration,
        before=before,
        after=audit_snapshot(alteration),
        company_id=alteration.company_id,
        request=request,
        metadata={"reopen_operation": bool(reopen_operation)},
    )
    return alteration


@transaction.atomic
def record_customer_validation(
    *, fitting, decision, actor, customer_name="", notes="", evidence_reference="", request=None
):
    fitting = FittingSession.objects.select_for_update().select_related("order", "company", "organization").get(pk=fitting.pk)
    if hasattr(fitting, "customer_validation"):
        raise ValidationError("This fitting already has a customer validation record.")
    validation = CustomerValidation(
        organization=fitting.organization,
        company=fitting.company,
        order=fitting.order,
        fitting=fitting,
        decision=decision,
        customer_name=customer_name,
        notes=notes,
        evidence_reference=evidence_reference,
        recorded_by=actor,
        validated_at=timezone.now(),
    )
    validation.full_clean()
    validation.save()
    record_audit_event(
        organization=validation.organization,
        actor=actor,
        action="fashion.customer_validation.record",
        object_instance=validation,
        after=audit_snapshot(validation),
        company_id=validation.company_id,
        request=request,
    )
    return validation


def order_delivery_readiness(order):
    blockers = []
    if order.status != order.Status.CONFIRMED:
        blockers.append("order_not_confirmed")
    if order.alteration_requests.filter(status__in=(AlterationRequest.Status.OPEN, AlterationRequest.Status.IN_PROGRESS)).exists():
        blockers.append("open_alterations")
    latest_required_fitting = (
        order.fitting_sessions.filter(requires_customer_validation=True)
        .exclude(status=FittingSession.Status.CANCELLED)
        .order_by("-performed_at", "-scheduled_at", "-created_at")
        .first()
    )
    if latest_required_fitting:
        if latest_required_fitting.status != FittingSession.Status.COMPLETED:
            blockers.append("fitting_not_completed")
        elif latest_required_fitting.result != FittingSession.Result.FIT_OK:
            blockers.append("fit_not_accepted")
        else:
            try:
                validation = latest_required_fitting.customer_validation
            except CustomerValidation.DoesNotExist:
                blockers.append("customer_validation_missing")
            else:
                if validation.decision != CustomerValidation.Decision.APPROVED:
                    blockers.append("customer_validation_rejected")
    return {"deliverable": not blockers, "blockers": blockers}
