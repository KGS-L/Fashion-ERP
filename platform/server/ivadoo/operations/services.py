import hashlib
import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ivadoo.audit.services import audit_snapshot, record_audit_event

from .models import ApprovalRule, StockMovementApproval


def resolve_approval_rule(*, organization, resource, action, value, company=None, establishment=None, warehouse=None):
    value = Decimal(value)
    rules = ApprovalRule.objects.filter(
        organization=organization,
        resource=resource,
        action=action,
        is_active=True,
        threshold__lte=value,
    ).select_related("company", "establishment", "warehouse")
    candidates = []
    for rule in rules:
        if rule.company_id and (not company or rule.company_id != company.id):
            continue
        if rule.establishment_id and (not establishment or rule.establishment_id != establishment.id):
            continue
        if rule.warehouse_id and (not warehouse or rule.warehouse_id != warehouse.id):
            continue
        specificity = int(bool(rule.company_id)) + int(bool(rule.establishment_id)) + int(bool(rule.warehouse_id))
        candidates.append((specificity, rule.threshold, rule))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def purchase_order_total(purchase_order):
    return sum((Decimal(line.quantity) * Decimal(line.unit_price) for line in purchase_order.lines.all()), Decimal("0"))


def assert_purchase_order_approver(*, purchase_order, actor):
    warehouse = purchase_order.warehouse
    establishment = warehouse.establishment if warehouse else None
    rule = resolve_approval_rule(
        organization=purchase_order.organization,
        resource=ApprovalRule.Resource.PURCHASE_ORDER,
        action="approve",
        value=purchase_order_total(purchase_order),
        company=purchase_order.company,
        establishment=establishment,
        warehouse=warehouse,
    )
    if rule and rule.require_distinct_approver and purchase_order.created_by_id == actor.id:
        raise ValidationError({"approver": "This approval rule requires an approver distinct from the purchase-order creator."})
    return rule


def _identifier(value):
    if value is None:
        return None
    return str(getattr(value, "id", value))


def canonical_stock_payload(data):
    payload = {
        "movement_type": str(data["movement_type"]),
        "quantity": str(Decimal(data["quantity"])),
        "product_id": _identifier(data["product"]),
        "product_variant_id": _identifier(data.get("product_variant")),
        "unit_id": _identifier(data["unit"]),
        "source_location_id": _identifier(data.get("source_location")),
        "destination_location_id": _identifier(data.get("destination_location")),
        "lot_id": _identifier(data.get("lot")),
        "reason": data.get("reason", ""),
        "reference_type": data.get("reference_type", ""),
        "reference_id": _identifier(data.get("reference_id")),
        "idempotency_key": data.get("idempotency_key", ""),
    }
    return payload


def stock_payload_digest(data):
    encoded = json.dumps(canonical_stock_payload(data), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stock_scope(data):
    location = data.get("source_location") or data.get("destination_location")
    if location is None:
        raise ValidationError("A stock approval requires a source or destination location.")
    warehouse = location.warehouse
    return warehouse.company, warehouse.establishment, warehouse


def stock_approval_rule(*, organization, data):
    company, establishment, warehouse = stock_scope(data)
    return resolve_approval_rule(
        organization=organization,
        resource=ApprovalRule.Resource.STOCK_MOVEMENT,
        action=str(data["movement_type"]),
        value=data["quantity"],
        company=company,
        establishment=establishment,
        warehouse=warehouse,
    )


@transaction.atomic
def create_stock_movement_approval(*, organization, actor, data, request=None):
    rule = stock_approval_rule(organization=organization, data=data)
    if rule is None:
        raise ValidationError({"approval": "No active approval rule applies to this stock movement."})
    company, establishment, warehouse = stock_scope(data)
    payload = canonical_stock_payload(data)
    digest = stock_payload_digest(data)
    key = data.get("idempotency_key", "")
    if not key:
        raise ValidationError({"idempotency_key": "Approved stock movements require an idempotency key."})
    existing = StockMovementApproval.objects.select_for_update().filter(organization=organization, idempotency_key=key).first()
    if existing:
        if existing.payload_digest != digest:
            raise ValidationError({"idempotency_key": "This approval idempotency key is already bound to a different payload."})
        return existing
    approval = StockMovementApproval(
        organization=organization,
        company=company,
        establishment=establishment,
        warehouse=warehouse,
        movement_type=data["movement_type"],
        quantity=data["quantity"],
        payload=payload,
        payload_digest=digest,
        idempotency_key=key,
        requested_by=actor,
    )
    approval.full_clean()
    approval.save()
    record_audit_event(
        organization=organization,
        actor=actor,
        action="operations.stock_approval.request",
        object_instance=approval,
        after=audit_snapshot(approval),
        company_id=company.id,
        request=request,
    )
    return approval


@transaction.atomic
def decide_stock_movement_approval(*, approval, actor, decision, reason="", request=None):
    approval = StockMovementApproval.objects.select_for_update().select_related("organization", "company", "establishment", "warehouse", "requested_by").get(pk=approval.pk)
    target = {
        "approve": StockMovementApproval.Status.APPROVED,
        "reject": StockMovementApproval.Status.REJECTED,
        "cancel": StockMovementApproval.Status.CANCELLED,
    }.get(decision)
    if target is None:
        raise ValidationError({"decision": "Unsupported approval decision."})
    if approval.status == target:
        return approval
    if approval.status != StockMovementApproval.Status.PENDING:
        raise ValidationError({"status": "Only pending approvals can be decided."})
    if decision in {"reject", "cancel"} and not reason.strip():
        raise ValidationError({"reason": "A reason is required for rejection or cancellation."})
    rule = resolve_approval_rule(
        organization=approval.organization,
        resource=ApprovalRule.Resource.STOCK_MOVEMENT,
        action=approval.movement_type,
        value=approval.quantity,
        company=approval.company,
        establishment=approval.establishment,
        warehouse=approval.warehouse,
    )
    if decision == "approve" and rule and rule.require_distinct_approver and approval.requested_by_id == actor.id:
        raise ValidationError({"approver": "This approval rule requires an approver distinct from the requester."})
    before = audit_snapshot(approval)
    approval.status = target
    approval.decided_by = actor
    approval.decision_reason = reason.strip()
    approval.decided_at = timezone.now()
    approval.save(update_fields=("status", "decided_by", "decision_reason", "decided_at", "updated_at"))
    record_audit_event(
        organization=approval.organization,
        actor=actor,
        action=f"operations.stock_approval.{decision}",
        object_instance=approval,
        before=before,
        after=audit_snapshot(approval),
        company_id=approval.company_id,
        request=request,
    )
    return approval


def assert_stock_movement_approval(*, organization, data, approval_id):
    rule = stock_approval_rule(organization=organization, data=data)
    if rule is None:
        return None
    if not data.get("idempotency_key"):
        raise ValidationError({"idempotency_key": "Approved stock movements require an idempotency key."})
    if not approval_id:
        raise ValidationError({"approval_id": "An approved stock-movement approval is required by the configured threshold."})
    try:
        approval = StockMovementApproval.objects.select_for_update().get(id=approval_id, organization=organization)
    except StockMovementApproval.DoesNotExist as exc:
        raise ValidationError({"approval_id": "Approval was not found in this organization."}) from exc
    if approval.status != StockMovementApproval.Status.APPROVED:
        raise ValidationError({"approval_id": "Approval is not approved."})
    if approval.payload_digest != stock_payload_digest(data):
        raise ValidationError({"approval_id": "Approval payload does not match this stock movement."})
    if approval.consumed_at and not approval.consumed_movement_id:
        raise ValidationError({"approval_id": "Approval has already been consumed."})
    return approval


def consume_stock_movement_approval(*, approval, movement):
    if approval is None:
        return
    if approval.consumed_at:
        if approval.consumed_movement_id != movement.id:
            raise ValidationError({"approval_id": "Approval has already been consumed by another movement."})
        return
    approval.consumed_at = timezone.now()
    approval.consumed_movement_id = movement.id
    approval.save(update_fields=("consumed_at", "consumed_movement_id", "updated_at"))
