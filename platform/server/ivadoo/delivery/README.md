# Delivery

Phase 3 delivery workflow after production, quality and any required customer fitting/validation.

The module covers preparation, packages, pickup or local delivery, simple courier/reference assignment, controlled statuses and immutable timestamped proof. Deliveries may be partial by order line and quantity. The order delivery-balance endpoint exposes allocated, delivered, returned, exchange allowance and remaining quantities without mutating the Phase 2 sales-order lifecycle.

Finished goods leave inventory only when pickup or local delivery is completed with proof. The stock issue is immutable, idempotent and linked to the delivery line. Returns preserve the original delivery/proof history and create explicit inbound stock movements. A returned item can be restocked, moved to an explicit `receiving` location used as return quarantine, or returned then marked damaged. Exchanges reopen only the returned exchange quantity for a replacement delivery; they do not silently create a replacement order or alter accounting.

Critical quantity checks lock the sales order lines and inventory positions server-side so concurrent deliveries/returns cannot over-deliver or over-return an order line. Return requests require an idempotency key.

No logistics costing, payroll, advanced carrier integration, refund accounting or Phase 4+ functionality is introduced here.
