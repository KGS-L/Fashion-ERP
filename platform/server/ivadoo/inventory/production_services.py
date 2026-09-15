from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ivadoo.audit.services import audit_snapshot, record_audit_event

from .models import StockMovement, StockReservation
from .services import _apply_lot_delta, _lock_lot, _locked_position, _save_position


ZERO = Decimal("0")


def consumed_reservation_quantity(reservation):
    return (
        StockMovement.objects.filter(
            organization=reservation.organization,
            movement_type=StockMovement.MovementType.PRODUCTION_CONSUMPTION,
            reference_type="inventory.stock_reservation",
            reference_id=reservation.id,
        ).aggregate(total=Sum("quantity"))["total"]
        or ZERO
    )


@transaction.atomic
def consume_reserved_quantity(
    *, reservation, quantity, actor, idempotency_key, reason="", request=None
):
    quantity = Decimal(quantity)
    if quantity <= ZERO:
        raise ValidationError("Consumed quantity must be greater than zero.")
    if not idempotency_key:
        raise ValidationError("An idempotency key is required for partial production consumption.")

    movement_key = f"production-reservation:{idempotency_key}"
    existing = StockMovement.objects.filter(
        organization=reservation.organization,
        idempotency_key=movement_key,
    ).first()
    if existing:
        return existing, StockReservation.objects.get(pk=reservation.pk)

    reservation = (
        StockReservation.objects.select_for_update(of=("self",))
        .select_related(
            "organization",
            "company",
            "warehouse",
            "location",
            "product",
            "product_variant",
            "unit",
            "lot",
        )
        .get(pk=reservation.pk)
    )
    existing = StockMovement.objects.filter(
        organization=reservation.organization,
        idempotency_key=movement_key,
    ).first()
    if existing:
        return existing, reservation
    if reservation.status == StockReservation.Status.RELEASED:
        raise ValidationError("Released reservations cannot be consumed.")
    if reservation.status == StockReservation.Status.CONSUMED:
        raise ValidationError("Reservation is already fully consumed.")

    already_consumed = consumed_reservation_quantity(reservation)
    remaining = reservation.quantity - already_consumed
    if remaining <= ZERO:
        raise ValidationError("Reservation has no remaining quantity to consume.")
    if quantity > remaining:
        raise ValidationError("Consumption exceeds the remaining reserved quantity.")

    position = _locked_position(
        organization=reservation.organization,
        location=reservation.location,
        product=reservation.product,
        product_variant=reservation.product_variant,
        unit=reservation.unit,
    )
    if reservation.status == StockReservation.Status.ACTIVE:
        if position.quantity_reserved < quantity:
            raise ValidationError("Reserved stock is inconsistent with the requested consumption.")
        position.quantity_reserved -= quantity
    elif reservation.status == StockReservation.Status.IN_PRODUCTION:
        if position.quantity_in_production < quantity:
            raise ValidationError("Production stock is inconsistent with the requested consumption.")
        position.quantity_in_production -= quantity
    else:
        raise ValidationError("Reservation is not consumable.")
    _save_position(position)

    lot = _lock_lot(reservation.lot)
    _apply_lot_delta(lot, -quantity)
    movement = StockMovement.objects.create(
        organization=reservation.organization,
        company=reservation.company,
        source_location=reservation.location,
        product=reservation.product,
        product_variant=reservation.product_variant,
        unit=reservation.unit,
        lot=lot,
        movement_type=StockMovement.MovementType.PRODUCTION_CONSUMPTION,
        quantity=quantity,
        reason=reason or "Reserved material consumed in production",
        reference_type="inventory.stock_reservation",
        reference_id=reservation.id,
        idempotency_key=movement_key,
        created_by=actor,
    )

    before = audit_snapshot(reservation)
    if already_consumed + quantity == reservation.quantity:
        reservation.status = StockReservation.Status.CONSUMED
        reservation.consumed_at = timezone.now()
        reservation.save(update_fields=("status", "consumed_at", "updated_at"))
    record_audit_event(
        organization=reservation.organization,
        actor=actor,
        action="inventory.reservation.consume_partial",
        object_instance=reservation,
        before=before,
        after=audit_snapshot(reservation),
        request=request,
        metadata={
            "movement_id": str(movement.id),
            "quantity": str(quantity),
            "remaining_quantity": str(remaining - quantity),
        },
    )
    return movement, reservation
