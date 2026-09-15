# Inventory

Phase 3 inventory domain for Ivadoo.

The module owns warehouses, internal stock locations, read-only calculated stock positions, lots/rolls/reusable remnants, immutable stock movements and material reservations.

## Invariants

- stock quantities are never edited through generic CRUD;
- every physical increase/decrease/transfer is performed by a transactional service and creates an immutable `StockMovement`;
- positions distinguish available, reserved, in-production, damaged and subcontractor quantities;
- reservations use row locking and cannot allocate more than available stock;
- movement and reservation idempotency keys prevent duplicate application of critical actions;
- lots keep their origin and remaining quantity, while quantity changes are derived from authorized stock operations;
- company and establishment scopes are enforced server-side.

The subcontractor stock bucket is present only as a structural state. Complete subcontracting workflows remain outside Phase 3.
