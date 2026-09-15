from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ivadoo.audit.services import audit_snapshot, record_audit_event
from ivadoo.inventory.models import StockLocation, StockMovement, StockPosition
from ivadoo.inventory.services import apply_stock_movement
from ivadoo.manufacturing.production_models import ManufacturingOutputReceipt
from ivadoo.quality.services import assert_quality_gate_passed
from ivadoo.sales.fitting_services import order_delivery_readiness
from ivadoo.sales.models import Order, OrderLine

from .models import (
    Delivery,
    DeliveryProof,
    DeliveryReturn,
    DeliveryReturnLine,
    DeliveryReturnStockAllocation,
)


ZERO = Decimal("0")
ACTIVE_DELIVERY_STATUSES = (
    Delivery.Status.DRAFT,
    Delivery.Status.PREPARED,
    Delivery.Status.ASSIGNED,
    Delivery.Status.SHIPPED,
    Delivery.Status.READY_FOR_PICKUP,
    Delivery.Status.PICKED_UP,
    Delivery.Status.DELIVERED,
)
TERMINAL_DELIVERY_STATUSES = (Delivery.Status.PICKED_UP, Delivery.Status.DELIVERED)


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
    ).select_related(
        "manufacturing_order",
        "destination_location__warehouse",
        "product",
        "product_variant",
        "unit",
    )
    if not receipts.exists() and order.lines.count() == 1:
        receipts = ManufacturingOutputReceipt.objects.filter(
            manufacturing_order__order=order,
            manufacturing_order__order_line__isnull=True,
            manufacturing_order__status="done",
        ).select_related(
            "manufacturing_order",
            "destination_location__warehouse",
            "product",
            "product_variant",
            "unit",
        )
    return receipts.order_by("created_at", "id")


def _exchange_allowance(order_line):
    return (
        DeliveryReturnLine.objects.filter(
            delivery_line__order_line=order_line,
            delivery_return__resolution=DeliveryReturn.Resolution.EXCHANGE,
        ).aggregate(total=Sum("quantity"))["total"]
        or ZERO
    )


def _allocated_quantity(order_line, *, exclude_delivery_id=None):
    queryset = order_line.delivery_lines.filter(delivery__status__in=ACTIVE_DELIVERY_STATUSES)
    if exclude_delivery_id:
        queryset = queryset.exclude(delivery_id=exclude_delivery_id)
    return queryset.aggregate(total=Sum("quantity"))["total"] or ZERO


def _delivered_quantity(order_line):
    return (
        order_line.delivery_lines.filter(delivery__status__in=TERMINAL_DELIVERY_STATUSES)
        .aggregate(total=Sum("quantity"))["total"]
        or ZERO
    )


def _returned_quantity(order_line):
    return (
        DeliveryReturnLine.objects.filter(delivery_line__order_line=order_line)
        .aggregate(total=Sum("quantity"))["total"]
        or ZERO
    )


def order_delivery_balance(order):
    lines = []
    all_allocated = True
    for order_line in order.lines.all().order_by("id"):
        ordered = Decimal(order_line.quantity)
        exchange_allowance = _exchange_allowance(order_line)
        allocated = _allocated_quantity(order_line)
        delivered = _delivered_quantity(order_line)
        returned = _returned_quantity(order_line)
        remaining_to_allocate = max(ZERO, ordered + exchange_allowance - allocated)
        if remaining_to_allocate > ZERO:
            all_allocated = False
        lines.append(
            {
                "order_line_id": str(order_line.id),
                "ordered_quantity": ordered,
                "allocated_quantity": allocated,
                "delivered_quantity": delivered,
                "returned_quantity": returned,
                "exchange_allowance_quantity": exchange_allowance,
                "remaining_to_allocate": remaining_to_allocate,
                "customer_net_quantity": max(ZERO, delivered - returned),
            }
        )
    has_in_flight = Delivery.objects.filter(order=order, status__in=(
        Delivery.Status.DRAFT,
        Delivery.Status.PREPARED,
        Delivery.Status.ASSIGNED,
        Delivery.Status.SHIPPED,
        Delivery.Status.READY_FOR_PICKUP,
    )).exists()
    return {
        "order_id": str(order.id),
        "fully_allocated": all_allocated,
        "operationally_complete": all_allocated and not has_in_flight,
        "lines": lines,
    }


def _approved_output_capacity(order, order_line):
    total = ZERO
    for receipt in _output_receipts_for_line(order, order_line):
        assert_quality_gate_passed(output_receipt=receipt)
        total += Decimal(receipt.quantity)
    return total


def validate_delivery(delivery):
    readiness = order_delivery_readiness(delivery.order)
    if not readiness["deliverable"]:
        raise ValidationError("Order is not delivery-ready: " + ", ".join(readiness["blockers"]))
    delivery_lines = list(delivery.lines.select_related("order_line").all())
    if not delivery_lines:
        raise ValidationError("At least one delivery line is required.")
    if not delivery.packages.exists():
        raise ValidationError("At least one package is required before preparation.")
    for line in delivery_lines:
        ordered = Decimal(line.order_line.quantity)
        exchange_allowance = _exchange_allowance(line.order_line)
        allocated = _allocated_quantity(line.order_line)
        if allocated > ordered + exchange_allowance:
            raise ValidationError(f"Order line {line.order_line_id} is over-allocated for delivery.")
        produced = _approved_output_capacity(delivery.order, line.order_line)
        if produced < allocated:
            raise ValidationError(
                f"Order line {line.order_line_id} has only {produced} quality-approved produced quantity for {allocated} allocated."
            )


def _issue_delivery_stock(delivery, actor, request=None):
    for line in delivery.lines.select_related("order_line").all():
        already_issued = (
            StockMovement.objects.filter(
                organization=delivery.organization,
                movement_type=StockMovement.MovementType.ISSUE,
                reference_type="delivery.delivery_line",
                reference_id=line.id,
            ).aggregate(total=Sum("quantity"))["total"]
            or ZERO
        )
        remaining = Decimal(line.quantity) - already_issued
        if remaining <= ZERO:
            continue
        for receipt in _output_receipts_for_line(delivery.order, line.order_line):
            if remaining <= ZERO:
                break
            assert_quality_gate_passed(output_receipt=receipt)
            position = StockPosition.objects.select_for_update().filter(
                organization=delivery.organization,
                location=receipt.destination_location,
                product=receipt.product,
                product_variant=receipt.product_variant,
                unit=receipt.unit,
            ).first()
            available = Decimal(position.quantity_available) if position else ZERO
            if available <= ZERO:
                continue
            quantity = min(remaining, available)
            apply_stock_movement(
                organization=delivery.organization,
                actor=actor,
                movement_type=StockMovement.MovementType.ISSUE,
                quantity=quantity,
                product=receipt.product,
                product_variant=receipt.product_variant,
                unit=receipt.unit,
                source_location=receipt.destination_location,
                reason=f"Delivery {delivery.number}",
                reference_type="delivery.delivery_line",
                reference_id=line.id,
                idempotency_key=f"delivery-issue:{line.id}:{receipt.id}",
                request=request,
            )
            remaining -= quantity
        if remaining > ZERO:
            raise ValidationError(f"Insufficient finished stock to complete delivery line {line.id}.")


@transaction.atomic
def create_delivery(*, order, number, mode, lines, packages, actor, courier_name="", courier_reference="", destination_notes="", request=None):
    order = Order.objects.select_for_update().select_related("organization", "company").get(pk=order.pk)
    if order.status != Order.Status.CONFIRMED:
        raise ValidationError("Deliveries can be created only for confirmed orders.")
    locked_lines = {line.id: line for line in OrderLine.objects.select_for_update().filter(order=order)}
    if not lines:
        raise ValidationError("At least one delivery line is required.")
    seen = set()
    normalized = []
    for item in lines:
        order_line = locked_lines.get(item["order_line"].id)
        if not order_line:
            raise ValidationError("Delivery line is outside the selected order.")
        if order_line.id in seen:
            raise ValidationError("An order line can appear only once in a delivery.")
        seen.add(order_line.id)
        quantity = Decimal(item["quantity"])
        if quantity <= ZERO:
            raise ValidationError("Delivery quantity must be greater than zero.")
        maximum = Decimal(order_line.quantity) + _exchange_allowance(order_line)
        remaining = maximum - _allocated_quantity(order_line)
        if quantity > remaining:
            raise ValidationError(
                f"Delivery quantity {quantity} exceeds remaining allocatable quantity {max(ZERO, remaining)} for order line {order_line.id}."
            )
        normalized.append((order_line, quantity))
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
    for order_line, quantity in normalized:
        line = delivery.lines.create(order_line=order_line, quantity=quantity)
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
    list(OrderLine.objects.select_for_update().filter(order=delivery.order).values_list("id", flat=True))
    before = delivery_snapshot(delivery)
    now = timezone.now()
    if action == "prepare":
        if delivery.status != Delivery.Status.DRAFT:
            raise ValidationError("Only draft deliveries can be prepared.")
        validate_delivery(delivery)
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
            if delivery.status == Delivery.Status.DELIVERED and hasattr(delivery, "proof"):
                return delivery
            if delivery.mode != Delivery.Mode.LOCAL_DELIVERY or delivery.status != Delivery.Status.SHIPPED:
                raise ValidationError("Only a shipped local delivery can be delivered.")
            terminal_status = Delivery.Status.DELIVERED
        else:
            if delivery.status == Delivery.Status.PICKED_UP and hasattr(delivery, "proof"):
                return delivery
            if delivery.mode != Delivery.Mode.PICKUP or delivery.status != Delivery.Status.READY_FOR_PICKUP:
                raise ValidationError("Only a ready pickup can be collected.")
            terminal_status = Delivery.Status.PICKED_UP
        if not proof:
            raise ValidationError("A timestamped delivery/pickup proof is required for completion.")
        if hasattr(delivery, "proof"):
            raise ValidationError("Delivery proof already exists.")
        _issue_delivery_stock(delivery, actor, request=request)
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


def _returned_against_issue(issue_movement):
    return (
        DeliveryReturnStockAllocation.objects.filter(delivery_issue_movement=issue_movement)
        .aggregate(total=Sum("quantity"))["total"]
        or ZERO
    )


def _validate_return_destination(*, delivery, disposition, destination_location):
    if destination_location:
        if destination_location.organization_id != delivery.organization_id or destination_location.company_id != delivery.company_id:
            raise ValidationError("Return destination is outside the delivery company scope.")
    if disposition == DeliveryReturnLine.Disposition.QUARANTINE:
        if not destination_location:
            raise ValidationError("Quarantine returns require a receiving location.")
        if destination_location.kind != StockLocation.Kind.RECEIVING:
            raise ValidationError("Quarantine returns must target a receiving location reserved for quarantine.")


def _apply_return_stock(*, return_line, actor, request=None):
    delivery_line = return_line.delivery_line
    source_issues = StockMovement.objects.select_for_update().filter(
        organization=return_line.delivery_return.organization,
        movement_type=StockMovement.MovementType.ISSUE,
        reference_type="delivery.delivery_line",
        reference_id=delivery_line.id,
    ).select_related("source_location__warehouse", "product", "product_variant", "unit").order_by("created_at", "id")
    remaining = Decimal(return_line.quantity)
    if not source_issues.exists():
        raise ValidationError("The delivery line has no traceable finished-stock issue movement.")
    for issue in source_issues:
        if remaining <= ZERO:
            break
        available_against_issue = Decimal(issue.quantity) - _returned_against_issue(issue)
        if available_against_issue <= ZERO:
            continue
        quantity = min(remaining, available_against_issue)
        destination = return_line.destination_location or issue.source_location
        _validate_return_destination(
            delivery=delivery_line.delivery,
            disposition=return_line.disposition,
            destination_location=destination,
        )
        return_movement = apply_stock_movement(
            organization=return_line.delivery_return.organization,
            actor=actor,
            movement_type=StockMovement.MovementType.RETURN_IN,
            quantity=quantity,
            product=issue.product,
            product_variant=issue.product_variant,
            unit=issue.unit,
            destination_location=destination,
            reason=f"Return {return_line.delivery_return.number}: {return_line.delivery_return.reason}",
            reference_type="delivery.return_line",
            reference_id=return_line.id,
            idempotency_key=f"delivery-return:{return_line.id}:{issue.id}:in",
            request=request,
        )
        damage_movement = None
        if return_line.disposition == DeliveryReturnLine.Disposition.DAMAGED:
            damage_movement = apply_stock_movement(
                organization=return_line.delivery_return.organization,
                actor=actor,
                movement_type=StockMovement.MovementType.DAMAGE,
                quantity=quantity,
                product=issue.product,
                product_variant=issue.product_variant,
                unit=issue.unit,
                source_location=destination,
                reason=f"Returned damaged item {return_line.delivery_return.number}",
                reference_type="delivery.return_line",
                reference_id=return_line.id,
                idempotency_key=f"delivery-return:{return_line.id}:{issue.id}:damage",
                request=request,
            )
        DeliveryReturnStockAllocation.objects.create(
            return_line=return_line,
            delivery_issue_movement=issue,
            return_movement=return_movement,
            damage_movement=damage_movement,
            quantity=quantity,
        )
        remaining -= quantity
    if remaining > ZERO:
        raise ValidationError("Return quantity exceeds the traceable delivered stock quantity.")


@transaction.atomic
def create_delivery_return(*, delivery, number, reason, resolution, idempotency_key, lines, actor, request=None):
    delivery = Delivery.objects.select_for_update().select_related("organization", "company", "order").get(pk=delivery.pk)
    existing = DeliveryReturn.objects.filter(
        organization=delivery.organization,
        idempotency_key=idempotency_key,
    ).first()
    if existing:
        return existing
    if delivery.status not in TERMINAL_DELIVERY_STATUSES:
        raise ValidationError("Returns can be recorded only for delivered or picked-up deliveries.")
    if not reason.strip():
        raise ValidationError("Return reason is required.")
    if not idempotency_key.strip():
        raise ValidationError("Idempotency key is required for returns and exchanges.")
    locked_delivery_lines = {
        item.id: item
        for item in delivery.lines.select_for_update().select_related("order_line").all()
    }
    delivery_return = DeliveryReturn(
        organization=delivery.organization,
        company=delivery.company,
        delivery=delivery,
        number=number,
        reason=reason,
        resolution=resolution,
        idempotency_key=idempotency_key,
        created_by=actor,
    )
    delivery_return.full_clean()
    delivery_return.save()
    seen = set()
    for item in lines:
        delivery_line = locked_delivery_lines.get(item["delivery_line"].id)
        if not delivery_line:
            raise ValidationError("Returned line is outside the selected delivery.")
        if delivery_line.id in seen:
            raise ValidationError("A delivery line can appear only once in a return.")
        seen.add(delivery_line.id)
        quantity = Decimal(item["quantity"])
        previously_returned = (
            DeliveryReturnLine.objects.filter(delivery_line=delivery_line)
            .aggregate(total=Sum("quantity"))["total"]
            or ZERO
        )
        if quantity <= ZERO or previously_returned + quantity > Decimal(delivery_line.quantity):
            raise ValidationError(
                f"Return quantity exceeds the remaining returnable quantity for delivery line {delivery_line.id}."
            )
        destination = item.get("destination_location")
        _validate_return_destination(
            delivery=delivery,
            disposition=item["disposition"],
            destination_location=destination,
        )
        return_line = DeliveryReturnLine(
            delivery_return=delivery_return,
            delivery_line=delivery_line,
            quantity=quantity,
            disposition=item["disposition"],
            destination_location=destination,
        )
        return_line.full_clean()
        return_line.save()
        _apply_return_stock(return_line=return_line, actor=actor, request=request)
    if not seen:
        raise ValidationError("At least one return line is required.")
    record_audit_event(
        organization=delivery_return.organization,
        actor=actor,
        action="delivery.return.record",
        object_instance=delivery_return,
        after=audit_snapshot(delivery_return),
        company_id=delivery_return.company_id,
        request=request,
        metadata={"resolution": resolution, "reason": reason},
    )
    return delivery_return
