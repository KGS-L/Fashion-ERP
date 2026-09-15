from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ivadoo.audit.services import record_audit_event
from ivadoo.inventory.models import StockMovement
from ivadoo.inventory.services import apply_stock_movement

from .models import (
    PurchaseOrderLine,
    PurchaseReceipt,
    PurchaseReceiptLine,
    SupplierProduct,
    SupplierPurchaseHistory,
)


ZERO = Decimal("0")


def _receipt_snapshot(receipt):
    return {
        "number": receipt.number,
        "purchase_order_id": str(receipt.purchase_order_id),
        "warehouse_id": str(receipt.warehouse_id),
        "status": receipt.status,
        "received_at": receipt.received_at.isoformat() if receipt.received_at else None,
        "controlled_at": receipt.controlled_at.isoformat() if receipt.controlled_at else None,
        "posted_at": receipt.posted_at.isoformat() if receipt.posted_at else None,
    }


@transaction.atomic
def control_receipt(*, receipt, decisions, actor, reason="", request=None):
    receipt = PurchaseReceipt.objects.select_for_update().select_related(
        "purchase_order", "warehouse"
    ).get(pk=receipt.pk)
    if receipt.status == PurchaseReceipt.Status.CONTROLLED:
        return receipt
    if receipt.status != PurchaseReceipt.Status.DRAFT:
        raise ValidationError("Only draft receipts can be quality-controlled.")

    lines = {
        str(line.id): line
        for line in PurchaseReceiptLine.objects.select_for_update()
        .filter(receipt=receipt)
        .select_related("purchase_order_line", "location")
    }
    supplied_ids = {str(decision["line_id"]) for decision in decisions}
    if supplied_ids != set(lines):
        raise ValidationError("Control decisions must cover every receipt line exactly once.")

    before = _receipt_snapshot(receipt)
    for decision in decisions:
        line = lines[str(decision["line_id"])]
        accepted = Decimal(decision["accepted_quantity"])
        rejected = Decimal(decision["rejected_quantity"])
        if accepted < ZERO or rejected < ZERO:
            raise ValidationError("Controlled quantities cannot be negative.")
        if accepted + rejected != line.received_quantity:
            raise ValidationError(
                "Accepted plus rejected quantity must equal the received quantity."
            )
        line.accepted_quantity = accepted
        line.rejected_quantity = rejected
        line.control_note = decision.get("note", "")
        if accepted == line.received_quantity:
            line.quality_status = PurchaseReceiptLine.QualityStatus.ACCEPTED
        elif rejected == line.received_quantity:
            line.quality_status = PurchaseReceiptLine.QualityStatus.REJECTED
        else:
            line.quality_status = PurchaseReceiptLine.QualityStatus.PARTIAL
        line.full_clean()
        line.save(
            update_fields=(
                "accepted_quantity",
                "rejected_quantity",
                "quality_status",
                "control_note",
                "updated_at",
            )
        )

    receipt.status = PurchaseReceipt.Status.CONTROLLED
    receipt.controlled_by = actor
    receipt.controlled_at = timezone.now()
    receipt.transition_reason = reason
    receipt.save(
        update_fields=(
            "status",
            "controlled_by",
            "controlled_at",
            "transition_reason",
            "updated_at",
        )
    )
    record_audit_event(
        organization=receipt.organization,
        actor=actor,
        action="purchase.receipt.control",
        object_instance=receipt,
        before=before,
        after=_receipt_snapshot(receipt),
        company_id=receipt.company_id,
        request=request,
    )
    return receipt


def _supplier_history_for_line(*, receipt, line):
    po = receipt.purchase_order
    po_line = line.purchase_order_line
    ordered_at = po.ordered_at
    if ordered_at:
        lead_time_days = max((receipt.received_at.date() - ordered_at.date()).days, 0)
    else:
        lead_time_days = 0
    on_time = None
    if po_line.expected_date:
        on_time = receipt.received_at.date() <= po_line.expected_date
    return SupplierPurchaseHistory.objects.create(
        receipt_line=line,
        organization=receipt.organization,
        company=receipt.company,
        supplier=po.supplier,
        product=po_line.product,
        product_variant=po_line.product_variant,
        unit=po_line.unit,
        currency=po.currency,
        unit_price=po_line.unit_price,
        ordered_quantity=po_line.quantity,
        received_quantity=line.received_quantity,
        accepted_quantity=line.accepted_quantity,
        rejected_quantity=line.rejected_quantity,
        expected_date=po_line.expected_date,
        received_at=receipt.received_at,
        ordered_at=ordered_at,
        lead_time_days=lead_time_days,
        on_time=on_time,
    )


def _update_supplier_product(*, receipt, line, lead_time_days):
    po = receipt.purchase_order
    po_line = line.purchase_order_line
    links = SupplierProduct.objects.filter(
        supplier=po.supplier,
        product=po_line.product,
    )
    if po_line.product_variant_id:
        links = links.filter(product_variant=po_line.product_variant)
    else:
        links = links.filter(product_variant__isnull=True)
    link = links.first()
    if not link:
        return
    link.last_unit_price = po_line.unit_price
    link.lead_time_days = lead_time_days
    link.save(update_fields=("last_unit_price", "lead_time_days", "updated_at"))


@transaction.atomic
def post_receipt(*, receipt, actor, reason="", request=None):
    receipt = PurchaseReceipt.objects.select_for_update().select_related(
        "purchase_order",
        "purchase_order__supplier",
        "purchase_order__currency",
        "warehouse",
    ).get(pk=receipt.pk)
    if receipt.status == PurchaseReceipt.Status.POSTED:
        return receipt
    if receipt.status != PurchaseReceipt.Status.CONTROLLED:
        raise ValidationError("Only controlled receipts can be posted to stock.")

    before = _receipt_snapshot(receipt)
    lines = list(
        PurchaseReceiptLine.objects.select_for_update()
        .filter(receipt=receipt)
        .select_related(
            "purchase_order_line",
            "purchase_order_line__product",
            "purchase_order_line__product_variant",
            "purchase_order_line__unit",
            "location",
            "location__warehouse",
        )
    )
    if not lines:
        raise ValidationError("Receipt has no lines.")

    for line in lines:
        if line.accepted_quantity + line.rejected_quantity != line.received_quantity:
            raise ValidationError("Every receipt line must be fully controlled before posting.")
        po_line = PurchaseOrderLine.objects.select_for_update().select_related(
            "product", "product_variant", "unit"
        ).get(pk=line.purchase_order_line_id)
        outstanding = po_line.quantity - po_line.received_quantity
        if line.received_quantity > outstanding:
            raise ValidationError(
                "Receipt exceeds the open purchase quantity; cancel/recreate or use a later explicit override workflow."
            )

        if line.accepted_quantity > ZERO:
            movement = apply_stock_movement(
                organization=receipt.organization,
                actor=actor,
                movement_type=StockMovement.MovementType.RECEIPT,
                quantity=line.accepted_quantity,
                product=po_line.product,
                product_variant=po_line.product_variant,
                unit=po_line.unit,
                destination_location=line.location,
                reason=f"Accepted purchase receipt {receipt.number}",
                reference_type="purchases.receipt_line",
                reference_id=line.id,
                idempotency_key=f"purchase-receipt:{receipt.id}:line:{line.id}",
                request=request,
            )
            line.stock_movement = movement
            line.save(update_fields=("stock_movement", "updated_at"))

        po_line.received_quantity += line.accepted_quantity
        po_line.full_clean()
        po_line.save(update_fields=("received_quantity",))

        history, created = SupplierPurchaseHistory.objects.get_or_create(
            receipt_line=line,
            defaults={
                "organization": receipt.organization,
                "company": receipt.company,
                "supplier": receipt.purchase_order.supplier,
                "product": po_line.product,
                "product_variant": po_line.product_variant,
                "unit": po_line.unit,
                "currency": receipt.purchase_order.currency,
                "unit_price": po_line.unit_price,
                "ordered_quantity": po_line.quantity,
                "received_quantity": line.received_quantity,
                "accepted_quantity": line.accepted_quantity,
                "rejected_quantity": line.rejected_quantity,
                "expected_date": po_line.expected_date,
                "received_at": receipt.received_at,
                "ordered_at": receipt.purchase_order.ordered_at,
                "lead_time_days": max(
                    (
                        receipt.received_at.date()
                        - receipt.purchase_order.ordered_at.date()
                    ).days,
                    0,
                )
                if receipt.purchase_order.ordered_at
                else 0,
                "on_time": (
                    receipt.received_at.date() <= po_line.expected_date
                    if po_line.expected_date
                    else None
                ),
            },
        )
        if created:
            _update_supplier_product(
                receipt=receipt,
                line=line,
                lead_time_days=history.lead_time_days,
            )

    receipt.status = PurchaseReceipt.Status.POSTED
    receipt.posted_by = actor
    receipt.posted_at = timezone.now()
    receipt.transition_reason = reason
    receipt.save(
        update_fields=(
            "status",
            "posted_by",
            "posted_at",
            "transition_reason",
            "updated_at",
        )
    )
    record_audit_event(
        organization=receipt.organization,
        actor=actor,
        action="purchase.receipt.post",
        object_instance=receipt,
        before=before,
        after=_receipt_snapshot(receipt),
        company_id=receipt.company_id,
        request=request,
    )
    return receipt


@transaction.atomic
def cancel_receipt(*, receipt, actor, reason="", request=None):
    receipt = PurchaseReceipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status == PurchaseReceipt.Status.CANCELLED:
        return receipt
    if receipt.status == PurchaseReceipt.Status.POSTED:
        raise ValidationError("Posted receipts cannot be cancelled; a compensating stock flow is required.")
    before = _receipt_snapshot(receipt)
    receipt.status = PurchaseReceipt.Status.CANCELLED
    receipt.cancelled_at = timezone.now()
    receipt.transition_reason = reason
    receipt.save(
        update_fields=(
            "status",
            "cancelled_at",
            "transition_reason",
            "updated_at",
        )
    )
    record_audit_event(
        organization=receipt.organization,
        actor=actor,
        action="purchase.receipt.cancel",
        object_instance=receipt,
        before=before,
        after=_receipt_snapshot(receipt),
        company_id=receipt.company_id,
        request=request,
    )
    return receipt
