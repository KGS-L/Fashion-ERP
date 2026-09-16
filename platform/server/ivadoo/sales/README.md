# Sales

Phase 2 custom-order quotations and orders are extended in Phase 3 with fitting sessions, customer-requested alterations and customer validation before delivery.

Order measurement snapshots are frozen at confirmation. Fitting and alteration records capture subsequent fit observations and requested adjustments separately; they never rewrite the confirmed measurement snapshot.

Phase 3 exposes delivery-readiness checks so later delivery workflows can block shipment while required customer validation is missing or an alteration remains open. Manufacturing rework can be explicitly linked and reopened only through the manufacturing transition permission.

## Phase 4 commercial order types

Orders now have an explicit `order_type`: `custom`, `series` or `wholesale`. The default remains `custom`, preserving the Phase 2 made-to-measure flow.

Series and wholesale lines use `variant_quantities` to express the quantity matrix by fashion-model variant. Variant metadata already carries size and color. The sum of the variant quantities must equal the order-line quantity, every variant must belong to the selected fashion model and the commercial company scope is enforced. Customer measurement sets remain exclusive to custom orders.

Commercial customization is stored as structured JSON on both the order line and, when needed, a specific variant quantity. `discount_rate` is bounded between 0 and 1. `delivery_date` and `event_date` are separate; when both are present, delivery cannot be scheduled after the event.

`fulfillment_mode` (`auto`, `finished_stock`, `production`) is a commercial fulfillment intent. It does not itself create stock movements or manufacturing orders. The Phase 4 series-production workflow consumes this intent when linking sales to finished stock or production, while partial deliveries continue to use the existing delivery-line quantities.

At confirmation, Ivadoo freezes an immutable commercial snapshot containing the order type, line/variant matrix, commercial customization and totals. This keeps the commercial basis traceable even if catalog data changes later.

## Controlled confirmation rules

The shared operational `ApprovalRule` registry accepts the `sales_order` resource with two actions:

- `confirm_amount`: threshold is compared with the order total after line discounts;
- `confirm_discount`: threshold is compared with the highest line discount rate.

When a matching rule exists, confirmation requires the scoped `fashion.sale.approve` permission. If `require_distinct_approver` is enabled, the order creator cannot approve their own controlled confirmation. Without a matching rule, the existing `fashion.sale.manage` confirmation flow remains unchanged.
