from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from ivadoo.audit.services import audit_snapshot, record_audit_event

from .models import QualityCriterion, QualityInspection, QualityRework


def inspection_snapshot(inspection):
    return {
        "inspection_type": inspection.inspection_type,
        "status": inspection.status,
        "decision": inspection.decision,
        "blocking": inspection.blocking,
        "purchase_receipt_line_id": str(inspection.purchase_receipt_line_id) if inspection.purchase_receipt_line_id else None,
        "manufacturing_order_id": str(inspection.manufacturing_order_id) if inspection.manufacturing_order_id else None,
        "manufacturing_operation_id": str(inspection.manufacturing_operation_id) if inspection.manufacturing_operation_id else None,
        "output_receipt_id": str(inspection.output_receipt_id) if inspection.output_receipt_id else None,
        "parent_inspection_id": str(inspection.parent_inspection_id) if inspection.parent_inspection_id else None,
        "completed_at": inspection.completed_at.isoformat() if inspection.completed_at else None,
    }


@transaction.atomic
def complete_inspection(*, inspection, decision, actor, reason="", rework_instructions="", request=None):
    inspection = QualityInspection.objects.select_for_update().get(pk=inspection.pk)
    if inspection.status == QualityInspection.Status.COMPLETED:
        return inspection
    pending = inspection.criteria.filter(result=QualityCriterion.Result.PENDING).exists()
    if pending:
        raise ValidationError("Every quality criterion must be evaluated before completion.")
    failed = inspection.criteria.filter(result=QualityCriterion.Result.FAIL).exists()
    has_defects = inspection.defects.exists()
    if decision == QualityInspection.Decision.ACCEPT and (failed or has_defects):
        raise ValidationError("An inspection with failed criteria or recorded defects cannot be accepted.")
    if decision in (QualityInspection.Decision.REJECT, QualityInspection.Decision.REWORK) and not reason.strip():
        raise ValidationError("Reject and rework decisions require an explicit reason.")
    if decision == QualityInspection.Decision.REWORK and not rework_instructions.strip():
        raise ValidationError("Rework decision requires instructions.")
    if decision == QualityInspection.Decision.PENDING:
        raise ValidationError("A completed inspection cannot keep a pending decision.")

    before = inspection_snapshot(inspection)
    inspection.status = QualityInspection.Status.COMPLETED
    inspection.decision = decision
    inspection.completed_by = actor
    inspection.completed_at = timezone.now()
    inspection.completion_reason = reason
    inspection.save(update_fields=("status", "decision", "completed_by", "completed_at", "completion_reason", "updated_at"))

    if decision == QualityInspection.Decision.REWORK:
        QualityRework.objects.create(
            organization=inspection.organization,
            company=inspection.company,
            inspection=inspection,
            manufacturing_operation=inspection.manufacturing_operation,
            instructions=rework_instructions,
            created_by=actor,
        )
    record_audit_event(
        organization=inspection.organization,
        actor=actor,
        action="quality.inspection.complete",
        object_instance=inspection,
        before=before,
        after=inspection_snapshot(inspection),
        company_id=inspection.company_id,
        request=request,
        metadata={"decision": decision, "reason": reason},
    )
    return inspection


@transaction.atomic
def complete_rework(*, rework, actor, result_notes="", request=None):
    rework = QualityRework.objects.select_for_update().select_related("inspection").get(pk=rework.pk)
    if rework.status == QualityRework.Status.DONE:
        return rework
    before = audit_snapshot(rework)
    rework.status = QualityRework.Status.DONE
    rework.result_notes = result_notes
    rework.completed_by = actor
    rework.completed_at = timezone.now()
    rework.save(update_fields=("status", "result_notes", "completed_by", "completed_at", "updated_at"))
    record_audit_event(
        organization=rework.organization,
        actor=actor,
        action="quality.rework.complete",
        object_instance=rework,
        before=before,
        after=audit_snapshot(rework),
        company_id=rework.company_id,
        request=request,
    )
    return rework


def _latest_blocking_inspection(**context):
    return (
        QualityInspection.objects.filter(status=QualityInspection.Status.COMPLETED, blocking=True, **context)
        .order_by("-completed_at", "-created_at")
        .first()
    )


def assert_quality_gate_passed(**context):
    inspection = _latest_blocking_inspection(**context)
    if inspection and inspection.decision != QualityInspection.Decision.ACCEPT:
        raise ValidationError(f"Quality gate blocked by inspection {inspection.id} with decision {inspection.decision}.")
    return inspection


def quality_summary(queryset):
    completed = queryset.filter(status=QualityInspection.Status.COMPLETED)
    aggregates = completed.aggregate(
        total=Count("id", distinct=True),
        accepted=Count("id", filter=Q(decision=QualityInspection.Decision.ACCEPT), distinct=True),
        rejected=Count("id", filter=Q(decision=QualityInspection.Decision.REJECT), distinct=True),
        rework=Count("id", filter=Q(decision=QualityInspection.Decision.REWORK), distinct=True),
        with_defects=Count("id", filter=Q(defects__isnull=False), distinct=True),
        defect_count=Count("defects"),
    )
    total = aggregates["total"] or 0
    with_defects = aggregates["with_defects"] or 0
    aggregates["defect_rate_percent"] = round((with_defects * 100 / total), 2) if total else 0
    return aggregates
