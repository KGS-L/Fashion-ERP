from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ivadoo.audit.services import audit_snapshot, record_audit_event

from .models import PurchaseOrder, PurchaseRequest, RequestForQuotation, SupplierQuotation


def _record_transition(*, instance, actor, action, before, request=None):
    record_audit_event(
        organization=instance.organization,
        actor=actor,
        action=action,
        object_instance=instance,
        before=before,
        after=audit_snapshot(instance),
        request=request,
    )


@transaction.atomic
def transition_purchase_request(*, purchase_request, action, actor, reason="", request=None):
    instance = PurchaseRequest.objects.select_for_update().get(pk=purchase_request.pk)
    before = audit_snapshot(instance)
    now = timezone.now()
    allowed = {
        "submit": ({PurchaseRequest.Status.DRAFT}, PurchaseRequest.Status.SUBMITTED),
        "approve": ({PurchaseRequest.Status.SUBMITTED}, PurchaseRequest.Status.APPROVED),
        "reject": ({PurchaseRequest.Status.SUBMITTED}, PurchaseRequest.Status.REJECTED),
        "cancel": ({PurchaseRequest.Status.DRAFT, PurchaseRequest.Status.SUBMITTED, PurchaseRequest.Status.APPROVED}, PurchaseRequest.Status.CANCELLED),
    }
    if action not in allowed:
        raise ValidationError({"action": "Unsupported purchase request action."})
    origins, target = allowed[action]
    if instance.status == target:
        return instance
    if instance.status not in origins:
        raise ValidationError({"status": f"Action {action!r} is not allowed from status {instance.status!r}."})
    if action in {"reject", "cancel"} and not reason.strip():
        raise ValidationError({"reason": "A reason is required for rejection or cancellation."})
    if action == "submit" and not instance.lines.exists():
        raise ValidationError({"lines": "A purchase request must contain at least one line before submission."})
    instance.status = target
    instance.transition_reason = reason.strip()
    update_fields = ["status", "transition_reason", "updated_at"]
    if action == "submit":
        instance.submitted_at = now
        update_fields.append("submitted_at")
    elif action == "approve":
        instance.approved_at = now
        instance.approved_by = actor
        update_fields.extend(("approved_at", "approved_by"))
    elif action == "reject":
        instance.rejected_at = now
        update_fields.append("rejected_at")
    elif action == "cancel":
        instance.cancelled_at = now
        update_fields.append("cancelled_at")
    instance.save(update_fields=update_fields)
    _record_transition(instance=instance, actor=actor, action=f"purchase.request.{action}", before=before, request=request)
    return instance


@transaction.atomic
def transition_rfq(*, rfq, action, actor, reason="", request=None):
    instance = RequestForQuotation.objects.select_for_update().get(pk=rfq.pk)
    before = audit_snapshot(instance)
    now = timezone.now()
    allowed = {
        "send": ({RequestForQuotation.Status.DRAFT}, RequestForQuotation.Status.SENT),
        "close": ({RequestForQuotation.Status.SENT}, RequestForQuotation.Status.CLOSED),
        "cancel": ({RequestForQuotation.Status.DRAFT, RequestForQuotation.Status.SENT}, RequestForQuotation.Status.CANCELLED),
    }
    if action not in allowed:
        raise ValidationError({"action": "Unsupported RFQ action."})
    origins, target = allowed[action]
    if instance.status == target:
        return instance
    if instance.status not in origins:
        raise ValidationError({"status": f"Action {action!r} is not allowed from status {instance.status!r}."})
    if action == "cancel" and not reason.strip():
        raise ValidationError({"reason": "A reason is required for RFQ cancellation."})
    if action == "send" and not instance.supplier_links.exists():
        raise ValidationError({"supplier_ids": "At least one supplier must be invited before sending the RFQ."})
    instance.status = target
    instance.transition_reason = reason.strip()
    update_fields = ["status", "transition_reason", "updated_at"]
    if action == "send":
        instance.sent_at = now
        update_fields.append("sent_at")
    elif action == "close":
        instance.closed_at = now
        update_fields.append("closed_at")
    elif action == "cancel":
        instance.cancelled_at = now
        update_fields.append("cancelled_at")
    instance.save(update_fields=update_fields)
    _record_transition(instance=instance, actor=actor, action=f"purchase.rfq.{action}", before=before, request=request)
    return instance


@transaction.atomic
def select_supplier_quotation(*, quotation, actor, request=None):
    instance = SupplierQuotation.objects.select_for_update().select_related("rfq", "supplier").get(pk=quotation.pk)
    if instance.rfq.status not in {RequestForQuotation.Status.SENT, RequestForQuotation.Status.CLOSED}:
        raise ValidationError({"rfq": "A quotation can only be selected for a sent or closed RFQ."})
    before = audit_snapshot(instance)
    SupplierQuotation.objects.filter(rfq=instance.rfq, status=SupplierQuotation.Status.SELECTED).exclude(pk=instance.pk).update(status=SupplierQuotation.Status.REJECTED)
    instance.status = SupplierQuotation.Status.SELECTED
    instance.save(update_fields=("status", "updated_at"))
    record_audit_event(
        organization=instance.rfq.organization,
        actor=actor,
        action="purchase.quotation.select",
        object_instance=instance,
        before=before,
        after=audit_snapshot(instance),
        company_id=instance.rfq.company_id,
        request=request,
    )
    return instance


@transaction.atomic
def transition_purchase_order(*, purchase_order, action, actor, reason="", request=None):
    instance = PurchaseOrder.objects.select_for_update().get(pk=purchase_order.pk)
    before = audit_snapshot(instance)
    now = timezone.now()
    allowed = {
        "submit": ({PurchaseOrder.Status.DRAFT}, PurchaseOrder.Status.PENDING_APPROVAL),
        "approve": ({PurchaseOrder.Status.PENDING_APPROVAL}, PurchaseOrder.Status.APPROVED),
        "order": ({PurchaseOrder.Status.APPROVED}, PurchaseOrder.Status.ORDERED),
        "cancel": ({PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.PENDING_APPROVAL, PurchaseOrder.Status.APPROVED, PurchaseOrder.Status.ORDERED}, PurchaseOrder.Status.CANCELLED),
    }
    if action not in allowed:
        raise ValidationError({"action": "Unsupported purchase order action."})
    origins, target = allowed[action]
    if instance.status == target:
        return instance
    if instance.status not in origins:
        raise ValidationError({"status": f"Action {action!r} is not allowed from status {instance.status!r}."})
    if action == "cancel" and not reason.strip():
        raise ValidationError({"reason": "A reason is required for purchase order cancellation."})
    if action == "submit" and not instance.lines.exists():
        raise ValidationError({"lines": "A purchase order must contain at least one line before submission."})
    instance.status = target
    instance.transition_reason = reason.strip()
    update_fields = ["status", "transition_reason", "updated_at"]
    if action == "submit":
        instance.submitted_at = now
        update_fields.append("submitted_at")
    elif action == "approve":
        instance.approved_at = now
        instance.approved_by = actor
        update_fields.extend(("approved_at", "approved_by"))
    elif action == "order":
        instance.ordered_at = now
        update_fields.append("ordered_at")
    elif action == "cancel":
        instance.cancelled_at = now
        update_fields.append("cancelled_at")
    instance.save(update_fields=update_fields)
    _record_transition(instance=instance, actor=actor, action=f"purchase.order.{action}", before=before, request=request)
    return instance
