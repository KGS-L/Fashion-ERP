from decimal import Decimal, ROUND_HALF_UP

from rest_framework.exceptions import PermissionDenied

from ivadoo.authorization.services import has_permission
from ivadoo.operations.models import ApprovalRule
from ivadoo.operations.services import resolve_approval_rule

from .models import OrderCommercialSnapshot


FOUR_DECIMAL_PLACES = Decimal("0.0001")


def _four_decimal(value):
    return Decimal(value).quantize(FOUR_DECIMAL_PLACES, rounding=ROUND_HALF_UP)


def order_amounts(order):
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    for line in order.lines.all():
        gross = Decimal(line.quantity) * Decimal(line.unit_price)
        discount = gross * Decimal(line.discount_rate)
        subtotal += gross
        discount_total += discount
    subtotal = _four_decimal(subtotal)
    discount_total = _four_decimal(discount_total)
    total = _four_decimal(subtotal - discount_total)
    return subtotal, discount_total, total


def order_max_discount_rate(order):
    rates = [Decimal(line.discount_rate) for line in order.lines.all()]
    return max(rates, default=Decimal("0"))


def applicable_confirmation_rules(order):
    subtotal, discount_total, total = order_amounts(order)
    amount_rule = resolve_approval_rule(
        organization=order.organization,
        resource=ApprovalRule.Resource.SALES_ORDER,
        action="confirm_amount",
        value=total,
        company=order.company,
    )
    discount_rule = resolve_approval_rule(
        organization=order.organization,
        resource=ApprovalRule.Resource.SALES_ORDER,
        action="confirm_discount",
        value=order_max_discount_rate(order),
        company=order.company,
    )
    return {
        "amount": amount_rule,
        "discount": discount_rule,
        "subtotal": subtotal,
        "discount_total": discount_total,
        "total": total,
    }


def assert_order_confirmation_rules(*, order, actor):
    resolved = applicable_confirmation_rules(order)
    rules = [rule for rule in (resolved["amount"], resolved["discount"]) if rule]
    if not rules:
        return resolved

    if not has_permission(
        actor,
        "fashion.sale.approve",
        company=order.company,
    ):
        raise PermissionDenied(
            "This order matches a configured amount or discount approval rule."
        )

    if any(rule.require_distinct_approver for rule in rules):
        if order.created_by_id and order.created_by_id == actor.id:
            raise PermissionDenied(
                "This sales approval rule requires an approver distinct from the order creator."
            )
    return resolved


def commercial_snapshot_payload(order):
    lines = []
    for line in order.lines.all():
        variant_quantities = []
        for allocation in line.variant_quantities.all():
            variant = allocation.model_variant
            variant_quantities.append(
                {
                    "model_variant_id": str(variant.id),
                    "variant_code": variant.code,
                    "size": variant.size,
                    "color": variant.color,
                    "quantity": str(allocation.quantity),
                    "commercial_customization": allocation.commercial_customization,
                }
            )
        lines.append(
            {
                "order_line_id": str(line.id),
                "fashion_model_id": (
                    str(line.fashion_model_id) if line.fashion_model_id else None
                ),
                "model_variant_id": (
                    str(line.model_variant_id) if line.model_variant_id else None
                ),
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "discount_rate": str(line.discount_rate),
                "fulfillment_mode": line.fulfillment_mode,
                "commercial_customization": line.commercial_customization,
                "variant_quantities": variant_quantities,
            }
        )
    return {
        "order_number": order.number,
        "order_type": order.order_type,
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "event_date": order.event_date.isoformat() if order.event_date else None,
        "lines": lines,
    }


def create_commercial_snapshot(*, order, actor, resolved=None):
    if resolved is None:
        resolved = applicable_confirmation_rules(order)
    snapshot = OrderCommercialSnapshot(
        order=order,
        order_type=order.order_type,
        subtotal=resolved["subtotal"],
        discount_total=resolved["discount_total"],
        total=resolved["total"],
        payload=commercial_snapshot_payload(order),
        confirmed_by=actor,
    )
    snapshot.full_clean()
    snapshot.save()
    return snapshot
