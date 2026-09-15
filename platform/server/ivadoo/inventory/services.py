from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from ivadoo.audit.services import audit_snapshot, record_audit_event

from .models import StockLot, StockMovement, StockPosition, StockReservation


ZERO = Decimal("0")


def _validate_item_scope(*, organization, product, product_variant, unit):
    if product.organization_id != organization.id:
        raise ValidationError("Product is outside the local organization.")
    if product_variant and product_variant.product_id != product.id:
        raise ValidationError("Product variant does not belong to the selected product.")
    if unit.organization_id != organization.id:
        raise ValidationError("Unit is outside the local organization.")
    if product.unit.category != unit.category:
        raise ValidationError("Unit category must match the product unit category.")


def _position_key(*, organization, location, product, product_variant, unit):
    return {
        "organization": organization,
        "warehouse": location.warehouse,
        "location": location,
        "product": product,
        "product_variant": product_variant,
        "unit": unit,
    }


def _locked_position(*, organization, location, product, product_variant, unit):
    key = _position_key(
        organization=organization,
        location=location,
        product=product,
        product_variant=product_variant,
        unit=unit,
    )
    try:
        position = StockPosition.objects.select_for_update().get(
            organization=organization,
            location=location,
            product=product,
            product_variant=product_variant,
            unit=unit,
        )
    except StockPosition.DoesNotExist:
        try:
            StockPosition.objects.create(**key)
        except IntegrityError:
            pass
        position = StockPosition.objects.select_for_update().get(
            organization=organization,
            location=location,
            product=product,
            product_variant=product_variant,
            unit=unit,
        )
    return position


def _save_position(position):
    position.full_clean()
    position.save(
        update_fields=(
            "quantity_available",
            "quantity_reserved",
            "quantity_in_production",
            "quantity_damaged",
            "quantity_subcontractor",
            "updated_at",
        )
    )


def _lock_lot(lot):
    if not lot:
        return None
    return StockLot.objects.select_for_update().get(pk=lot.pk)


def _apply_lot_delta(lot, delta, *, destination_location=None):
    if not lot:
        return
    new_remaining = lot.remaining_quantity + delta
    if new_remaining < ZERO:
        raise ValidationError("Lot remaining quantity cannot become negative.")
    if new_remaining > lot.initial_quantity:
        lot.initial_quantity = new_remaining
    lot.remaining_quantity = new_remaining
    if destination_location is not None:
        lot.location = destination_location
        lot.warehouse = destination_location.warehouse
    lot.status = StockLot.Status.EXHAUSTED if new_remaining == ZERO else StockLot.Status.ACTIVE
    if lot.initial_length is not None and lot.remaining_length is not None and lot.initial_quantity > ZERO:
        ratio = lot.remaining_quantity / lot.initial_quantity
        lot.remaining_length = (lot.initial_length * ratio).quantize(Decimal("0.0001"))
    lot.full_clean()
    lot.save()


@transaction.atomic
def create_lot_with_opening_stock(
    *, organization, actor, warehouse, location, product, unit, code, opening_quantity,
    product_variant=None, kind=StockLot.Kind.LOT, origin="", supplier_reference="",
    width=None, initial_length=None, reusable=True, request=None,
):
    quantity = Decimal(opening_quantity)
    if quantity <= ZERO:
        raise ValidationError("Opening quantity must be greater than zero.")
    _validate_item_scope(
        organization=organization,
        product=product,
        product_variant=product_variant,
        unit=unit,
    )
    if warehouse.organization_id != organization.id or location.warehouse_id != warehouse.id:
        raise ValidationError("Warehouse/location is outside the local organization.")
    lot = StockLot.objects.create(
        organization=organization,
        warehouse=warehouse,
        location=location,
        product=product,
        product_variant=product_variant,
        unit=unit,
        code=code,
        kind=kind,
        origin=origin,
        supplier_reference=supplier_reference,
        width=width,
        initial_length=initial_length,
        remaining_length=initial_length,
        initial_quantity=quantity,
        remaining_quantity=ZERO,
        reusable=reusable,
    )
    movement = apply_stock_movement(
        organization=organization,
        actor=actor,
        movement_type=StockMovement.MovementType.RECEIPT,
        quantity=quantity,
        product=product,
        product_variant=product_variant,
        unit=unit,
        destination_location=location,
        lot=lot,
        reason="Lot opening balance",
        reference_type="inventory.stock_lot",
        reference_id=lot.id,
        idempotency_key=f"lot-open:{lot.id}",
        request=request,
    )
    record_audit_event(
        organization=organization,
        actor=actor,
        action="inventory.lot.create",
        object_instance=lot,
        after=audit_snapshot(lot),
        request=request,
    )
    return lot, movement


@transaction.atomic
def apply_stock_movement(
    *, organization, actor, movement_type, quantity, product, unit,
    source_location=None, destination_location=None, product_variant=None, lot=None,
    reason="", reference_type="", reference_id=None, idempotency_key="", request=None,
):
    quantity = Decimal(quantity)
    if quantity <= ZERO:
        raise ValidationError("Movement quantity must be greater than zero.")
    _validate_item_scope(
        organization=organization,
        product=product,
        product_variant=product_variant,
        unit=unit,
    )
    if idempotency_key:
        existing = StockMovement.objects.filter(
            organization=organization,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            return existing

    if source_location and source_location.organization_id != organization.id:
        raise ValidationError("Source location is outside the local organization.")
    if destination_location and destination_location.organization_id != organization.id:
        raise ValidationError("Destination location is outside the local organization.")
    if source_location and destination_location and source_location.company_id != destination_location.company_id:
        raise ValidationError("Cross-company stock transfers are not allowed in Phase 3.")
    if lot:
        lot = _lock_lot(lot)
        if lot.organization_id != organization.id or lot.product_id != product.id:
            raise ValidationError("Lot is outside the movement item scope.")
        if product_variant and lot.product_variant_id not in (None, product_variant.id):
            raise ValidationError("Lot variant does not match the movement variant.")
        if lot.unit_id != unit.id:
            raise ValidationError("Lot unit does not match the movement unit.")

    inbound = {
        StockMovement.MovementType.RECEIPT,
        StockMovement.MovementType.ADJUSTMENT_IN,
        StockMovement.MovementType.RETURN_IN,
        StockMovement.MovementType.PRODUCTION_OUTPUT,
    }
    outbound = {
        StockMovement.MovementType.ISSUE,
        StockMovement.MovementType.ADJUSTMENT_OUT,
        StockMovement.MovementType.PRODUCTION_CONSUMPTION,
    }

    company = None
    if movement_type in inbound:
        if destination_location is None:
            raise ValidationError("Destination location is required for an inbound movement.")
        company = destination_location.warehouse.company
        destination_position = _locked_position(
            organization=organization,
            location=destination_location,
            product=product,
            product_variant=product_variant,
            unit=unit,
        )
        destination_position.quantity_available += quantity
        _save_position(destination_position)
        _apply_lot_delta(lot, quantity, destination_location=destination_location)
    elif movement_type in outbound:
        if source_location is None:
            raise ValidationError("Source location is required for an outbound movement.")
        company = source_location.warehouse.company
        source_position = _locked_position(
            organization=organization,
            location=source_location,
            product=product,
            product_variant=product_variant,
            unit=unit,
        )
        if source_position.quantity_available < quantity:
            raise ValidationError("Insufficient available stock.")
        source_position.quantity_available -= quantity
        _save_position(source_position)
        _apply_lot_delta(lot, -quantity)
    elif movement_type == StockMovement.MovementType.TRANSFER:
        if source_location is None or destination_location is None:
            raise ValidationError("Source and destination locations are required for a transfer.")
        if source_location.id == destination_location.id:
            raise ValidationError("Transfer source and destination must be different.")
        company = source_location.warehouse.company
        source_position = _locked_position(
            organization=organization,
            location=source_location,
            product=product,
            product_variant=product_variant,
            unit=unit,
        )
        destination_position = _locked_position(
            organization=organization,
            location=destination_location,
            product=product,
            product_variant=product_variant,
            unit=unit,
        )
        if source_position.quantity_available < quantity:
            raise ValidationError("Insufficient available stock.")
        source_position.quantity_available -= quantity
        destination_position.quantity_available += quantity
        _save_position(source_position)
        _save_position(destination_position)
        _apply_lot_delta(lot, ZERO, destination_location=destination_location)
    elif movement_type == StockMovement.MovementType.DAMAGE:
        if source_location is None:
            raise ValidationError("Source location is required to mark stock damaged.")
        company = source_location.warehouse.company
        source_position = _locked_position(
            organization=organization,
            location=source_location,
            product=product,
            product_variant=product_variant,
            unit=unit,
        )
        if source_position.quantity_available < quantity:
            raise ValidationError("Insufficient available stock.")
        source_position.quantity_available -= quantity
        source_position.quantity_damaged += quantity
        _save_position(source_position)
    elif movement_type == StockMovement.MovementType.RESTORE_DAMAGE:
        if source_location is None:
            raise ValidationError("Source location is required to restore damaged stock.")
        company = source_location.warehouse.company
        source_position = _locked_position(
            organization=organization,
            location=source_location,
            product=product,
            product_variant=product_variant,
            unit=unit,
        )
        if source_position.quantity_damaged < quantity:
            raise ValidationError("Insufficient damaged stock.")
        source_position.quantity_damaged -= quantity
        source_position.quantity_available += quantity
        _save_position(source_position)
    else:
        raise ValidationError("Unsupported stock movement type.")

    movement = StockMovement.objects.create(
        organization=organization,
        company=company,
        source_location=source_location,
        destination_location=destination_location,
        product=product,
        product_variant=product_variant,
        unit=unit,
        lot=lot,
        movement_type=movement_type,
        quantity=quantity,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        created_by=actor,
    )
    record_audit_event(
        organization=organization,
        actor=actor,
        action=f"inventory.movement.{movement_type}",
        object_instance=movement,
        after=audit_snapshot(movement),
        request=request,
    )
    return movement


@transaction.atomic
def reserve_stock(
    *, organization, actor, location, product, unit, quantity, product_variant=None,
    lot=None, order=None, production_order_id=None, idempotency_key="", request=None,
):
    quantity = Decimal(quantity)
    if quantity <= ZERO:
        raise ValidationError("Reservation quantity must be greater than zero.")
    _validate_item_scope(
        organization=organization,
        product=product,
        product_variant=product_variant,
        unit=unit,
    )
    if idempotency_key:
        existing = StockReservation.objects.filter(
            organization=organization,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            return existing
    if order and order.organization_id != organization.id:
        raise ValidationError("Order is outside the local organization.")
    if lot:
        lot = _lock_lot(lot)
        if lot.location_id != location.id or lot.product_id != product.id:
            raise ValidationError("Lot does not match the reservation location/product.")
        if lot.remaining_quantity < quantity:
            raise ValidationError("Lot does not have enough remaining quantity.")
    position = _locked_position(
        organization=organization,
        location=location,
        product=product,
        product_variant=product_variant,
        unit=unit,
    )
    if position.quantity_available < quantity:
        raise ValidationError("Insufficient available stock for reservation.")
    position.quantity_available -= quantity
    position.quantity_reserved += quantity
    _save_position(position)
    reservation = StockReservation.objects.create(
        organization=organization,
        company=location.warehouse.company,
        warehouse=location.warehouse,
        location=location,
        product=product,
        product_variant=product_variant,
        unit=unit,
        lot=lot,
        order=order,
        production_order_id=production_order_id,
        quantity=quantity,
        idempotency_key=idempotency_key,
        created_by=actor,
    )
    record_audit_event(
        organization=organization,
        actor=actor,
        action="inventory.reservation.create",
        object_instance=reservation,
        after=audit_snapshot(reservation),
        request=request,
    )
    return reservation


@transaction.atomic
def start_reservation_production(*, reservation, actor, request=None):
    reservation = StockReservation.objects.select_for_update().get(pk=reservation.pk)
    if reservation.status == StockReservation.Status.IN_PRODUCTION:
        return reservation
    if reservation.status != StockReservation.Status.ACTIVE:
        raise ValidationError("Only active reservations can enter production.")
    position = _locked_position(
        organization=reservation.organization,
        location=reservation.location,
        product=reservation.product,
        product_variant=reservation.product_variant,
        unit=reservation.unit,
    )
    if position.quantity_reserved < reservation.quantity:
        raise ValidationError("Reserved stock is inconsistent with the reservation.")
    position.quantity_reserved -= reservation.quantity
    position.quantity_in_production += reservation.quantity
    _save_position(position)
    before = audit_snapshot(reservation)
    reservation.status = StockReservation.Status.IN_PRODUCTION
    reservation.save(update_fields=("status", "updated_at"))
    record_audit_event(
        organization=reservation.organization,
        actor=actor,
        action="inventory.reservation.start_production",
        object_instance=reservation,
        before=before,
        after=audit_snapshot(reservation),
        request=request,
    )
    return reservation


@transaction.atomic
def release_reservation(*, reservation, actor, request=None):
    reservation = StockReservation.objects.select_for_update().get(pk=reservation.pk)
    if reservation.status == StockReservation.Status.RELEASED:
        return reservation
    if reservation.status == StockReservation.Status.CONSUMED:
        raise ValidationError("Consumed reservations cannot be released.")
    position = _locked_position(
        organization=reservation.organization,
        location=reservation.location,
        product=reservation.product,
        product_variant=reservation.product_variant,
        unit=reservation.unit,
    )
    if reservation.status == StockReservation.Status.ACTIVE:
        if position.quantity_reserved < reservation.quantity:
            raise ValidationError("Reserved stock is inconsistent with the reservation.")
        position.quantity_reserved -= reservation.quantity
    elif reservation.status == StockReservation.Status.IN_PRODUCTION:
        if position.quantity_in_production < reservation.quantity:
            raise ValidationError("Production stock is inconsistent with the reservation.")
        position.quantity_in_production -= reservation.quantity
    position.quantity_available += reservation.quantity
    _save_position(position)
    before = audit_snapshot(reservation)
    reservation.status = StockReservation.Status.RELEASED
    reservation.released_at = timezone.now()
    reservation.save(update_fields=("status", "released_at", "updated_at"))
    record_audit_event(
        organization=reservation.organization,
        actor=actor,
        action="inventory.reservation.release",
        object_instance=reservation,
        before=before,
        after=audit_snapshot(reservation),
        request=request,
    )
    return reservation


@transaction.atomic
def consume_reservation(*, reservation, actor, request=None):
    reservation = StockReservation.objects.select_for_update().get(pk=reservation.pk)
    if reservation.status == StockReservation.Status.CONSUMED:
        return reservation
    if reservation.status == StockReservation.Status.RELEASED:
        raise ValidationError("Released reservations cannot be consumed.")
    position = _locked_position(
        organization=reservation.organization,
        location=reservation.location,
        product=reservation.product,
        product_variant=reservation.product_variant,
        unit=reservation.unit,
    )
    if reservation.status == StockReservation.Status.ACTIVE:
        if position.quantity_reserved < reservation.quantity:
            raise ValidationError("Reserved stock is inconsistent with the reservation.")
        position.quantity_reserved -= reservation.quantity
    else:
        if position.quantity_in_production < reservation.quantity:
            raise ValidationError("Production stock is inconsistent with the reservation.")
        position.quantity_in_production -= reservation.quantity
    _save_position(position)
    lot = _lock_lot(reservation.lot)
    _apply_lot_delta(lot, -reservation.quantity)
    movement = StockMovement.objects.create(
        organization=reservation.organization,
        company=reservation.company,
        source_location=reservation.location,
        product=reservation.product,
        product_variant=reservation.product_variant,
        unit=reservation.unit,
        lot=lot,
        movement_type=StockMovement.MovementType.PRODUCTION_CONSUMPTION,
        quantity=reservation.quantity,
        reason="Reserved material consumed",
        reference_type="inventory.stock_reservation",
        reference_id=reservation.id,
        idempotency_key=f"reservation-consume:{reservation.id}",
        created_by=actor,
    )
    before = audit_snapshot(reservation)
    reservation.status = StockReservation.Status.CONSUMED
    reservation.consumed_at = timezone.now()
    reservation.save(update_fields=("status", "consumed_at", "updated_at"))
    record_audit_event(
        organization=reservation.organization,
        actor=actor,
        action="inventory.reservation.consume",
        object_instance=reservation,
        before=before,
        after=audit_snapshot(reservation),
        request=request,
        metadata={"movement_id": str(movement.id)},
    )
    return reservation
