from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ivadoo.audit.services import audit_snapshot, record_audit_event
from ivadoo.manufacturing.production_models import ManufacturingOutputReceipt
from ivadoo.quality.services import assert_quality_gate_passed
from ivadoo.sales.fitting_services import order_delivery_readiness
from ivadoo.sales.models import Order

from .models import Delivery, DeliveryProof


ZERO = Decimal("0")


def delivery_snapshot(delivery):
    return {
        "number": delivery.number,
        "order_id": str(delivery.order_id),
        "mode": delivery.mode,
        "status": delivery.status,
        "courier_name": delivery.courier_name,
        "courier_reference": delivery.courier_reference,
        "prepared_at": delivery.prepared_at.isoformat() if delivery.prepared_at else None,
        "assigned_at": delivery.assigned_at.isoformat() if delivery.assigned_at else None,
        "shipped_at": delivery.shipped_at.isoformat() if delivery.shipped_at else None,
        "completed_at": delivery.completed_at.isoformat() if delivery.completed_at else None,
        "failed_at": delivery.failed_at.isoformat() if delivery.failed_at else None,
    }


def _output_receipts_for_line(order, order_line):
    receipts = ManufacturingOutputReceipt.objects.filter(
        manufacturing_order__order=order,
        manufacturing_order__order_line=order_line,
        manufacturing_order__status="done",
    ).select_related("manufacturing_order")
    if not receipts.exists() and order.lines.count() == 1:
        receipts = ManufacturingOutputReceipt.objects.filter(
            manufacturing_order__order=order,
            manufacturing_order__order_line__isnull=True,
            manufacturing_order__status="done",
        ).select_related("manufacturing_order")
    return receipts


def validate_full_delivery(delivery):
    readiness = order_delivery_readiness(delivery.order)
    if not readiness["deliverable"]:
        raise ValidationError(
            "Order is not delivery-ready: " + ", ".join(readiness["blockers"])
        )
    order_lines = {line.id: line for line in delivery.order.lines.all()}
    delivery_lines = list(delivery.lines.select_related("order_line").all())
    if not order_lines or {line.order_line_id for line in delivery_lines} != set(order_lines):
        raise ValidationError("Phase 3 delivery must cover every order line exactly once.")
    if not delivery.packages.exists():
        raise ValidationError("At least one package is required before preparation.")
    for line in delivery_lines:
        ordered_quantity = Decimal(line.order_line.quantity)
        if line.quantity != ordered_quantity:
            raise ValidationError("Partial delivery quantities are deferred to issue #63.")
        receipts = _output_receipts_for_line(delivery.order, line.order_line)
        produced = receipts.aggregate(total=Sum("quantity"))["total"] or ZERO
        if produced < line.quantity:
            raise ValidationError(
                f"Order line {line.order_line_id} has only {produced} produced quantity available for {line.quantity} requested."
            )
        for receipt in receipts:
            assert_quality_gate_passed(output_receipt=receipt)


@transaction.atomic
def create_delivery(*, order, number, mode, lines, packages, actor, courier_name="", courier_reference="", destination_notes="", request=None):
    order = Order.objects.select_for_update().select_related("organization", "company").get(pk=order.pk)
    if order.status != Order.Status.CONFIRMED:
        raise ValidationError("Deliveries can be created only for confirmed orders.")
    if Delivery.objects.filter(order=order).exclude(status__in=(Delivery.Status.CANCELLED, Delivery.Status.FAILED)).exists():
        raise ValidationError("Phase 3 supports one active delivery per order; partial deliveries are deferred to issue #63.")
    delivery = Delivery(
        organization=order.organization,
        company=order.company,
        order=order,
        number=number,
        mode=mode,
        courier_name=courier_name,
        courier_reference=courier_reference,
        destination_notes=destination_notes,
        created_by=actor,
    )
    delivery.full_clean()
    delivery.save()
    seen = set()
    for item in lines:
        order_line = item["order_line"]
        if order_line.id in seen:
            raise ValidationError("An order line can appear only once in a Phase 3 delivery.")
        seen.add(order_line.id)
        if order_line.order_id != order.id:
            raise ValidationError("Delivery line is outside the selected order.")
        line = delivery.lines.create(order_line=order_line, quantity=item["quantity"])
        line.full_clean()
    for item in packages:
        delivery.packages.create(**item)
    record_audit_event(
        organization=delivery.organization,
        actor=actor,
        action="delivery.create",
        object_instance=delivery,
        after=delivery_snapshot(delivery),
        company_id=delivery.company_id,
        request=request,
    )
    return delivery


@transaction.atomic
def transition_delivery(*, delivery, action, actor, proof=None, failure_reason="", request=None):
    delivery = Delivery.objects.select_for_update().select_related("order").get(pk=delivery.pk)
    before = delivery_snapshot(delivery)
    now = timezone.now()
    if action == "prepare":
        if delivery.status != Delivery.Status.DRAFT:
            raise ValidationError("Only draft deliveries can be prepared.")
        validate_full_delivery(delivery)
        delivery.status = Delivery.Status.PREPARED
        delivery.prepared_at = now
        fields = ("status", "prepared_at", "updated_at")
    elif action == "assign":
        if delivery.mode != Delivery.Mode.LOCAL_DELIVERY or delivery.status != Delivery.Status.PREPARED:
            raise ValidationError("Only a prepared local delivery can be assigned.")
        if not (delivery.courier_name.strip() or delivery.courier_reference.strip()):
            raise ValidationError("Courier name or transport reference is required before assignment.")
        delivery.status = Delivery.Status.ASSIGNED
        delivery.assigned_at = now
        fields = ("status", "assigned_at", "updated_at")
    elif action == "ship":
        if delivery.mode != Delivery.Mode.LOCAL_DELIVERY or delivery.status != Delivery.Status.ASSIGNED:
            raise ValidationError("Only an assigned local delivery can be shipped.")
        delivery.status = Delivery.Status.SHIPPED
        delivery.shipped_at = now
        fields = ("status", "shipped_at", "updated_at")
    elif action == "ready_for_pickup":
        if delivery.mode != Delivery.Mode.PICKUP or delivery.status != Delivery.Status.PREPARED:
            raise ValidationError("Only a prepared pickup can become ready for pickup.")
        delivery.status = Delivery.Status.READY_FOR_PICKUP
        fields = ("status", "updated_at")
    elif action in ("deliver", "pickup"):
        if action == "deliver":
            if delivery.mode != Delivery.Mode.LOCAL_DELIVERY or delivery.status != Delivery.Status.SHIPPED:
                raise ValidationError("Only a shipped local delivery can be delivered.")
            terminal_status = Delivery.Status.DELIVERED
        else:
            if delivery.mode != Delivery.Mode.PICKUP or delivery.status != Delivery.Status.READY_FOR_PICKUP:
                raise ValidationError("Only a ready pickup can be collected.")
            terminal_status = Delivery.Status.PICKED_UP
        if not proof:
            raise ValidationError("A timestamped delivery/pickup proof is required for completion.")
        if hasattr(delivery, "proof"):
            raise ValidationError("Delivery proof already exists.")
        DeliveryProof.objects.create(
            delivery=delivery,
            proof_type=proof["proof_type"],
            recipient_name=proof["recipient_name"],
            evidence_reference=proof.get("evidence_reference", ""),
            notes=proof.get("notes", ""),
            recorded_by=actor,
        )
        delivery.status = terminal_status
        delivery.completed_at = now
        fields = ("status", "completed_at", "updated_at")
    elif action == "fail":
        if delivery.mode != Delivery.Mode.LOCAL_DELIVERY or delivery.status not in (Delivery.Status.ASSIGNED, Delivery.Status.SHIPPED):
            raise ValidationError("Only an assigned or shipped local delivery can fail.")
        if not failure_reason.strip():
            raise ValidationError("Failed deliveries require an explicit reason.")
        delivery.status = Delivery.Status.FAILED
        delivery.failure_reason = failure_reason
        delivery.failed_at = now
        fields = ("status", "failure_reason", "failed_at", "updated_at")
    elif action == "cancel":
        if delivery.status in (Delivery.Status.SHIPPED, Delivery.Status.PICKED_UP, Delivery.Status.DELIVERED, Delivery.Status.FAILED, Delivery.Status.CANCELLED):
            raise ValidationError("This delivery can no longer be cancelled.")
        delivery.status = Delivery.Status.CANCELLED
        fields = ("status", "updated_at")
    else:
        raise ValidationError("Unsupported delivery action.")
    delivery.save(update_fields=fields)
    record_audit_event(
        organization=delivery.organization,
        actor=actor,
        action=f"delivery.{action}",
        object_instance=delivery,
        before=before,
        after=delivery_snapshot(delivery),
        company_id=delivery.company_id,
        request=request,
        metadata={"failure_reason": failure_reason} if failure_reason else None,
    )
    return delivery
