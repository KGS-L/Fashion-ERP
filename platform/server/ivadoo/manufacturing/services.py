from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ivadoo.audit.services import record_audit_event
from ivadoo.inventory.models import StockReservation
from ivadoo.inventory.services import reserve_stock

from .models import (
    BillOfMaterials,
    ManufacturingMaterialRequirement,
    ManufacturingOrder,
)


FOUR_PLACES = Decimal("0.0001")


def bom_snapshot(bom):
    return {
        "code": bom.code,
        "version": bom.version,
        "status": bom.status,
        "company_id": str(bom.company_id),
        "fashion_model_id": str(bom.fashion_model_id),
        "model_variant_id": str(bom.model_variant_id) if bom.model_variant_id else None,
        "batch_quantity": str(bom.batch_quantity),
    }


def manufacturing_order_snapshot(order):
    return {
        "number": order.number,
        "status": order.status,
        "bom_id": str(order.bom_id),
        "bom_version": order.bom.version,
        "sales_order_id": str(order.order_id) if order.order_id else None,
        "sales_order_line_id": str(order.order_line_id) if order.order_line_id else None,
        "planned_quantity": str(order.planned_quantity),
        "produced_quantity": str(order.produced_quantity),
    }


@transaction.atomic
def activate_bom(*, bom, actor, request=None):
    bom = BillOfMaterials.objects.select_for_update().get(pk=bom.pk)
    if bom.status == BillOfMaterials.Status.ACTIVE:
        return bom
    if bom.status != BillOfMaterials.Status.DRAFT:
        raise ValidationError("Only draft BOM versions can be activated.")
    if not bom.lines.exists():
        raise ValidationError("A BOM must contain at least one material line before activation.")
    before = bom_snapshot(bom)
    bom.status = BillOfMaterials.Status.ACTIVE
    bom.activated_at = timezone.now()
    bom.save(update_fields=("status", "activated_at", "updated_at"))
    record_audit_event(
        organization=bom.organization,
        actor=actor,
        action="manufacturing.bom.activate",
        object_instance=bom,
        before=before,
        after=bom_snapshot(bom),
        company_id=bom.company_id,
        request=request,
    )
    return bom


@transaction.atomic
def archive_bom(*, bom, actor, request=None):
    bom = BillOfMaterials.objects.select_for_update().get(pk=bom.pk)
    if bom.status == BillOfMaterials.Status.ARCHIVED:
        return bom
    before = bom_snapshot(bom)
    bom.status = BillOfMaterials.Status.ARCHIVED
    bom.archived_at = timezone.now()
    bom.save(update_fields=("status", "archived_at", "updated_at"))
    record_audit_event(
        organization=bom.organization,
        actor=actor,
        action="manufacturing.bom.archive",
        object_instance=bom,
        before=before,
        after=bom_snapshot(bom),
        company_id=bom.company_id,
        request=request,
    )
    return bom


@transaction.atomic
def create_manufacturing_order(*, actor, request=None, **validated_data):
    bom = BillOfMaterials.objects.select_for_update().prefetch_related("lines").get(
        pk=validated_data["bom"].pk
    )
    if bom.status != BillOfMaterials.Status.ACTIVE:
        raise ValidationError("Manufacturing orders require an active BOM version.")
    validated_data["bom"] = bom
    manufacturing_order = ManufacturingOrder.objects.create(
        created_by=actor,
        **validated_data,
    )
    for line in bom.lines.select_related("product", "product_variant", "unit").all():
        quantity_per_unit = (line.quantity / bom.batch_quantity).quantize(
            FOUR_PLACES,
            rounding=ROUND_HALF_UP,
        )
        planned_quantity = (
            quantity_per_unit
            * manufacturing_order.planned_quantity
            * (Decimal("1") + line.waste_rate)
        ).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        ManufacturingMaterialRequirement.objects.create(
            manufacturing_order=manufacturing_order,
            source_bom_line=line,
            product=line.product,
            product_variant=line.product_variant,
            unit=line.unit,
            quantity_per_unit=quantity_per_unit,
            waste_rate=line.waste_rate,
            planned_quantity=planned_quantity,
        )
    record_audit_event(
        organization=manufacturing_order.organization,
        actor=actor,
        action="manufacturing.order.create",
        object_instance=manufacturing_order,
        after=manufacturing_order_snapshot(manufacturing_order),
        company_id=manufacturing_order.company_id,
        request=request,
    )
    return manufacturing_order


@transaction.atomic
def transition_manufacturing_order(
    *,
    manufacturing_order,
    action,
    actor,
    reason="",
    produced_quantity=None,
    request=None,
):
    manufacturing_order = ManufacturingOrder.objects.select_for_update().select_related(
        "bom"
    ).get(pk=manufacturing_order.pk)
    if action == "ready":
        expected = ManufacturingOrder.Status.DRAFT
        target = ManufacturingOrder.Status.READY
    elif action == "start":
        expected = ManufacturingOrder.Status.READY
        target = ManufacturingOrder.Status.IN_PROGRESS
    elif action == "done":
        expected = ManufacturingOrder.Status.IN_PROGRESS
        target = ManufacturingOrder.Status.DONE
    elif action == "cancel":
        if manufacturing_order.status == ManufacturingOrder.Status.CANCELLED:
            return manufacturing_order
        if manufacturing_order.status == ManufacturingOrder.Status.DONE:
            raise ValidationError("Completed manufacturing orders cannot be cancelled.")
        expected = manufacturing_order.status
        target = ManufacturingOrder.Status.CANCELLED
    else:
        raise ValidationError("Unsupported manufacturing order action.")

    if manufacturing_order.status == target:
        return manufacturing_order
    if manufacturing_order.status != expected:
        raise ValidationError(
            f"Action {action} is not allowed from status {manufacturing_order.status}."
        )

    before = manufacturing_order_snapshot(manufacturing_order)
    now = timezone.now()
    manufacturing_order.status = target
    manufacturing_order.transition_reason = reason
    update_fields = ["status", "transition_reason", "updated_at"]
    if target == ManufacturingOrder.Status.IN_PROGRESS:
        manufacturing_order.actual_start = manufacturing_order.actual_start or now
        update_fields.append("actual_start")
    if target == ManufacturingOrder.Status.DONE:
        if produced_quantity is not None:
            produced_quantity = Decimal(produced_quantity)
            if (
                produced_quantity <= 0
                or produced_quantity > manufacturing_order.planned_quantity
            ):
                raise ValidationError(
                    "Produced quantity must be greater than zero and cannot exceed planned quantity."
                )
            manufacturing_order.produced_quantity = produced_quantity
        if manufacturing_order.produced_quantity <= 0:
            raise ValidationError(
                "A completed manufacturing order requires a produced quantity."
            )
        manufacturing_order.actual_end = now
        update_fields.extend(("produced_quantity", "actual_end"))
    manufacturing_order.full_clean()
    manufacturing_order.save(update_fields=tuple(dict.fromkeys(update_fields)))
    record_audit_event(
        organization=manufacturing_order.organization,
        actor=actor,
        action=f"manufacturing.order.{action}",
        object_instance=manufacturing_order,
        before=before,
        after=manufacturing_order_snapshot(manufacturing_order),
        company_id=manufacturing_order.company_id,
        request=request,
    )
    return manufacturing_order


@transaction.atomic
def reserve_manufacturing_materials(
    *, manufacturing_order, allocations, actor, request=None
):
    manufacturing_order = ManufacturingOrder.objects.select_for_update().select_related(
        "warehouse", "warehouse__company"
    ).get(pk=manufacturing_order.pk)
    if manufacturing_order.status != ManufacturingOrder.Status.READY:
        raise ValidationError(
            "Materials can be reserved only for a ready manufacturing order."
        )

    requirements = {
        str(requirement.id): requirement
        for requirement in manufacturing_order.material_requirements.select_related(
            "product", "product_variant", "unit"
        )
    }
    reservations = []
    for allocation in allocations:
        requirement = requirements.get(str(allocation["requirement_id"]))
        if not requirement:
            raise ValidationError(
                "Material requirement is outside this manufacturing order."
            )
        location = allocation["location"]
        lot = allocation.get("lot")
        quantity = Decimal(allocation["quantity"])
        idempotency_key = allocation["idempotency_key"]
        if location.warehouse_id != manufacturing_order.warehouse_id:
            raise ValidationError(
                "Reservation location must belong to the manufacturing order warehouse."
            )
        if lot and lot.location_id != location.id:
            raise ValidationError(
                "Reservation lot must belong to the selected location."
            )

        existing = StockReservation.objects.filter(
            organization=manufacturing_order.organization,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            if (
                existing.production_order_id != manufacturing_order.id
                or existing.product_id != requirement.product_id
                or existing.product_variant_id != requirement.product_variant_id
                or existing.unit_id != requirement.unit_id
            ):
                raise ValidationError(
                    "Reservation idempotency key is already used by another material allocation."
                )
            reservations.append(existing)
            continue

        reserved = StockReservation.objects.filter(
            organization=manufacturing_order.organization,
            production_order_id=manufacturing_order.id,
            product=requirement.product,
            product_variant=requirement.product_variant,
            unit=requirement.unit,
            status__in=(
                StockReservation.Status.ACTIVE,
                StockReservation.Status.IN_PRODUCTION,
            ),
        ).aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        if reserved + quantity > requirement.planned_quantity:
            raise ValidationError(
                "Reservation exceeds the manufacturing material requirement."
            )
        reservations.append(
            reserve_stock(
                organization=manufacturing_order.organization,
                actor=actor,
                location=location,
                product=requirement.product,
                product_variant=requirement.product_variant,
                unit=requirement.unit,
                quantity=quantity,
                lot=lot,
                order=manufacturing_order.order,
                production_order_id=manufacturing_order.id,
                idempotency_key=idempotency_key,
                request=request,
            )
        )
    record_audit_event(
        organization=manufacturing_order.organization,
        actor=actor,
        action="manufacturing.order.reserve_materials",
        object_instance=manufacturing_order,
        company_id=manufacturing_order.company_id,
        request=request,
        metadata={"reservation_ids": [str(item.id) for item in reservations]},
    )
    return reservations
