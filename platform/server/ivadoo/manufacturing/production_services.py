from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ivadoo.audit.services import record_audit_event
from ivadoo.inventory.models import (
    StockLot,
    StockMovement,
    StockReservation,
)
from ivadoo.inventory.production_services import consume_reserved_quantity
from ivadoo.inventory.services import apply_stock_movement

from .models import ManufacturingOperation, ManufacturingOrder
from .production_models import (
    ManufacturingMaterialConsumption,
    ManufacturingMaterialRemnant,
    ManufacturingOutputReceipt,
)


ZERO = Decimal("0")


def _locked_order(manufacturing_order):
    return (
        ManufacturingOrder.objects.select_for_update(of=("self",))
        .select_related(
            "organization",
            "company",
            "warehouse",
            "bom",
            "bom__output_product",
            "bom__output_product__unit",
            "bom__output_product_variant",
        )
        .get(pk=manufacturing_order.pk)
    )


def _locked_requirement(manufacturing_order, requirement_id):
    try:
        return manufacturing_order.material_requirements.select_for_update(
            of=("self",)
        ).select_related(
            "product", "product_variant", "unit"
        ).get(id=requirement_id)
    except manufacturing_order.material_requirements.model.DoesNotExist as exc:
        raise ValidationError("Material requirement is outside this manufacturing order.") from exc


@transaction.atomic
def consume_manufacturing_materials(
    *, manufacturing_order, allocations, actor, request=None
):
    manufacturing_order = _locked_order(manufacturing_order)
    if manufacturing_order.status != ManufacturingOrder.Status.IN_PROGRESS:
        raise ValidationError("Materials can be consumed only while the manufacturing order is in progress.")

    results = []
    for allocation in allocations:
        idempotency_key = allocation["idempotency_key"]
        existing = ManufacturingMaterialConsumption.objects.filter(
            organization=manufacturing_order.organization,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            if existing.manufacturing_order_id != manufacturing_order.id:
                raise ValidationError("Consumption idempotency key belongs to another manufacturing order.")
            results.append(existing)
            continue

        requirement = _locked_requirement(
            manufacturing_order, allocation["requirement_id"]
        )
        quantity = Decimal(allocation["quantity"])
        if quantity <= ZERO:
            raise ValidationError("Consumption quantity must be greater than zero.")
        disposition = allocation.get(
            "disposition", ManufacturingMaterialConsumption.Disposition.CONSUMED
        )
        reason = allocation.get("reason", "")
        if disposition == ManufacturingMaterialConsumption.Disposition.SCRAP and not reason.strip():
            raise ValidationError("Scrap/loss consumption requires an explicit reason.")

        reservation = allocation.get("reservation")
        if reservation:
            reservation = StockReservation.objects.get(pk=reservation.pk)
            if reservation.production_order_id != manufacturing_order.id:
                raise ValidationError("Reservation is outside this manufacturing order.")
            if (
                reservation.product_id != requirement.product_id
                or reservation.product_variant_id != requirement.product_variant_id
                or reservation.unit_id != requirement.unit_id
            ):
                raise ValidationError("Reservation does not match the material requirement.")
            supplied_lot = allocation.get("lot")
            if supplied_lot and supplied_lot.id != reservation.lot_id:
                raise ValidationError("Reserved consumption must use the reservation lot.")
            movement, reservation = consume_reserved_quantity(
                reservation=reservation,
                quantity=quantity,
                actor=actor,
                idempotency_key=idempotency_key,
                reason=reason,
                request=request,
            )
            source_location = reservation.location
            lot = reservation.lot
            source_type = ManufacturingMaterialConsumption.SourceType.RESERVED
        else:
            source_location = allocation.get("source_location")
            if not source_location:
                raise ValidationError("Supplemental consumption requires a source location.")
            if source_location.warehouse_id != manufacturing_order.warehouse_id:
                raise ValidationError("Supplemental source location must belong to the manufacturing order warehouse.")
            if not reason.strip():
                raise ValidationError("Supplemental consumption requires an explicit reason.")
            lot = allocation.get("lot")
            if lot and (
                lot.organization_id != manufacturing_order.organization_id
                or lot.location_id != source_location.id
                or lot.product_id != requirement.product_id
                or lot.product_variant_id != requirement.product_variant_id
                or lot.unit_id != requirement.unit_id
            ):
                raise ValidationError("Supplemental lot does not match the material requirement and location.")
            movement = apply_stock_movement(
                organization=manufacturing_order.organization,
                actor=actor,
                movement_type=StockMovement.MovementType.PRODUCTION_CONSUMPTION,
                quantity=quantity,
                product=requirement.product,
                product_variant=requirement.product_variant,
                unit=requirement.unit,
                source_location=source_location,
                lot=lot,
                reason=reason,
                reference_type="manufacturing.material_requirement",
                reference_id=requirement.id,
                idempotency_key=f"manufacturing-supplemental:{idempotency_key}",
                request=request,
            )
            source_type = ManufacturingMaterialConsumption.SourceType.SUPPLEMENTAL

        consumption = ManufacturingMaterialConsumption.objects.create(
            organization=manufacturing_order.organization,
            company=manufacturing_order.company,
            manufacturing_order=manufacturing_order,
            requirement=requirement,
            reservation=reservation,
            source_location=source_location,
            product=requirement.product,
            product_variant=requirement.product_variant,
            unit=requirement.unit,
            lot=lot,
            stock_movement=movement,
            source_type=source_type,
            disposition=disposition,
            quantity=quantity,
            reason=reason,
            idempotency_key=idempotency_key,
            created_by=actor,
        )
        record_audit_event(
            organization=manufacturing_order.organization,
            actor=actor,
            action="manufacturing.material.consume",
            object_instance=consumption,
            company_id=manufacturing_order.company_id,
            request=request,
            metadata={
                "source_type": source_type,
                "disposition": disposition,
                "quantity": str(quantity),
                "stock_movement_id": str(movement.id),
            },
        )
        results.append(consumption)
    return results


def material_variance(manufacturing_order):
    rows = []
    requirements = manufacturing_order.material_requirements.select_related(
        "product", "product_variant", "unit"
    ).all()
    for requirement in requirements:
        gross = (
            requirement.consumptions.aggregate(total=Sum("quantity"))["total"]
            or ZERO
        )
        scrap = (
            requirement.consumptions.filter(
                disposition=ManufacturingMaterialConsumption.Disposition.SCRAP
            ).aggregate(total=Sum("quantity"))["total"]
            or ZERO
        )
        remnant = (
            requirement.remnants.aggregate(total=Sum("quantity"))["total"] or ZERO
        )
        net = gross - remnant
        rows.append(
            {
                "requirement_id": requirement.id,
                "product_id": requirement.product_id,
                "product_variant_id": requirement.product_variant_id,
                "unit_id": requirement.unit_id,
                "planned_quantity": requirement.planned_quantity,
                "gross_consumed_quantity": gross,
                "scrap_quantity": scrap,
                "reusable_remnant_quantity": remnant,
                "net_consumed_quantity": net,
                "variance_quantity": net - requirement.planned_quantity,
            }
        )
    return rows


@transaction.atomic
def record_reusable_remnant(
    *,
    manufacturing_order,
    requirement_id,
    location,
    quantity,
    code,
    idempotency_key,
    actor,
    reason="",
    request=None,
):
    manufacturing_order = _locked_order(manufacturing_order)
    if manufacturing_order.status != ManufacturingOrder.Status.IN_PROGRESS:
        raise ValidationError("Reusable remnants can be recorded only while production is in progress.")
    existing = ManufacturingMaterialRemnant.objects.filter(
        organization=manufacturing_order.organization,
        idempotency_key=idempotency_key,
    ).first()
    if existing:
        if existing.manufacturing_order_id != manufacturing_order.id:
            raise ValidationError("Remnant idempotency key belongs to another manufacturing order.")
        return existing
    requirement = _locked_requirement(manufacturing_order, requirement_id)
    quantity = Decimal(quantity)
    if quantity <= ZERO:
        raise ValidationError("Remnant quantity must be greater than zero.")
    if location.warehouse_id != manufacturing_order.warehouse_id:
        raise ValidationError("Remnant location must belong to the manufacturing order warehouse.")
    gross_consumed = (
        requirement.consumptions.aggregate(total=Sum("quantity"))["total"] or ZERO
    )
    already_returned = (
        requirement.remnants.aggregate(total=Sum("quantity"))["total"] or ZERO
    )
    if already_returned + quantity > gross_consumed:
        raise ValidationError("Reusable remnants cannot exceed the material quantity already consumed.")
    if StockLot.objects.filter(
        organization=manufacturing_order.organization, code=code
    ).exists():
        raise ValidationError("Stock lot code already exists in this organization.")

    lot = StockLot.objects.create(
        organization=manufacturing_order.organization,
        warehouse=manufacturing_order.warehouse,
        location=location,
        product=requirement.product,
        product_variant=requirement.product_variant,
        unit=requirement.unit,
        code=code,
        kind=StockLot.Kind.REMNANT,
        origin=f"Manufacturing order {manufacturing_order.number}",
        initial_quantity=quantity,
        remaining_quantity=ZERO,
        reusable=True,
    )
    movement = apply_stock_movement(
        organization=manufacturing_order.organization,
        actor=actor,
        movement_type=StockMovement.MovementType.RETURN_IN,
        quantity=quantity,
        product=requirement.product,
        product_variant=requirement.product_variant,
        unit=requirement.unit,
        destination_location=location,
        lot=lot,
        reason=reason or f"Reusable remnant from manufacturing order {manufacturing_order.number}",
        reference_type="manufacturing.material_requirement",
        reference_id=requirement.id,
        idempotency_key=f"manufacturing-remnant:{idempotency_key}",
        request=request,
    )
    remnant = ManufacturingMaterialRemnant.objects.create(
        organization=manufacturing_order.organization,
        company=manufacturing_order.company,
        manufacturing_order=manufacturing_order,
        requirement=requirement,
        location=location,
        product=requirement.product,
        product_variant=requirement.product_variant,
        unit=requirement.unit,
        stock_lot=lot,
        stock_movement=movement,
        quantity=quantity,
        reason=reason,
        idempotency_key=idempotency_key,
        created_by=actor,
    )
    record_audit_event(
        organization=manufacturing_order.organization,
        actor=actor,
        action="manufacturing.material.remnant",
        object_instance=remnant,
        company_id=manufacturing_order.company_id,
        request=request,
        metadata={
            "quantity": str(quantity),
            "stock_lot_id": str(lot.id),
            "stock_movement_id": str(movement.id),
        },
    )
    return remnant


@transaction.atomic
def complete_manufacturing_order(
    *, manufacturing_order, produced_quantity, destination_location, actor, reason="", request=None
):
    manufacturing_order = _locked_order(manufacturing_order)
    existing = ManufacturingOutputReceipt.objects.filter(
        manufacturing_order=manufacturing_order
    ).select_related("stock_movement").first()
    if existing:
        if manufacturing_order.status != ManufacturingOrder.Status.DONE:
            raise ValidationError("Manufacturing output exists while the order is not completed.")
        return existing
    if manufacturing_order.status != ManufacturingOrder.Status.IN_PROGRESS:
        raise ValidationError("Only an in-progress manufacturing order can be completed.")
    if ManufacturingOperation.objects.filter(
        manufacturing_order=manufacturing_order
    ).exclude(
        status__in=(ManufacturingOperation.Status.DONE, ManufacturingOperation.Status.CANCELLED)
    ).exists():
        raise ValidationError("All manufacturing operations must be completed or cancelled before final output.")
    if StockReservation.objects.filter(
        organization=manufacturing_order.organization,
        production_order_id=manufacturing_order.id,
        status__in=(StockReservation.Status.ACTIVE, StockReservation.Status.IN_PRODUCTION),
    ).exists():
        raise ValidationError("All manufacturing material reservations must be consumed or released before final output.")

    output_product = manufacturing_order.bom.output_product
    output_variant = manufacturing_order.bom.output_product_variant
    if not output_product:
        raise ValidationError("The manufacturing BOM must define a finished output product before completion.")
    if destination_location.warehouse_id != manufacturing_order.warehouse_id:
        raise ValidationError("Finished output location must belong to the manufacturing order warehouse.")
    produced_quantity = Decimal(produced_quantity)
    if produced_quantity <= ZERO or produced_quantity > manufacturing_order.planned_quantity:
        raise ValidationError("Produced quantity must be greater than zero and cannot exceed planned quantity.")

    movement = apply_stock_movement(
        organization=manufacturing_order.organization,
        actor=actor,
        movement_type=StockMovement.MovementType.PRODUCTION_OUTPUT,
        quantity=produced_quantity,
        product=output_product,
        product_variant=output_variant,
        unit=output_product.unit,
        destination_location=destination_location,
        reason=reason or f"Finished output from manufacturing order {manufacturing_order.number}",
        reference_type="manufacturing.manufacturing_order",
        reference_id=manufacturing_order.id,
        idempotency_key=f"manufacturing-output:{manufacturing_order.id}",
        request=request,
    )
    receipt = ManufacturingOutputReceipt.objects.create(
        organization=manufacturing_order.organization,
        company=manufacturing_order.company,
        manufacturing_order=manufacturing_order,
        destination_location=destination_location,
        product=output_product,
        product_variant=output_variant,
        unit=output_product.unit,
        stock_movement=movement,
        quantity=produced_quantity,
        created_by=actor,
    )
    before = {
        "status": manufacturing_order.status,
        "produced_quantity": str(manufacturing_order.produced_quantity),
        "actual_end": manufacturing_order.actual_end.isoformat() if manufacturing_order.actual_end else None,
    }
    manufacturing_order.status = ManufacturingOrder.Status.DONE
    manufacturing_order.produced_quantity = produced_quantity
    manufacturing_order.actual_end = timezone.now()
    manufacturing_order.transition_reason = reason
    manufacturing_order.full_clean()
    manufacturing_order.save(
        update_fields=(
            "status",
            "produced_quantity",
            "actual_end",
            "transition_reason",
            "updated_at",
        )
    )
    record_audit_event(
        organization=manufacturing_order.organization,
        actor=actor,
        action="manufacturing.order.complete_production",
        object_instance=manufacturing_order,
        before=before,
        after={
            "status": manufacturing_order.status,
            "produced_quantity": str(manufacturing_order.produced_quantity),
            "actual_end": manufacturing_order.actual_end.isoformat(),
        },
        company_id=manufacturing_order.company_id,
        request=request,
        metadata={
            "output_receipt_id": str(receipt.id),
            "stock_movement_id": str(movement.id),
        },
    )
    return receipt
