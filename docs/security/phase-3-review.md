# Phase 3 — security and transactional integrity review

This review covers the operational domains that move quantities or advance protected business states: inventory, purchasing receipts, manufacturing consumption/output, quality decisions, delivery/returns and approval thresholds.

## Isolation and authorization

REST querysets are organization-scoped and narrowed by company/site permissions. Mutating endpoints re-check RBAC in the effective Company/Establishment/Warehouse context before invoking services. Serializers reject foreign organization/company objects. Contract and domain tests cover unauthenticated access, empty results without scope and cross-scope validation. Phase 3 introduces no raw import or custom-field path that bypasses the same domain services.

## Transactional invariants

Stock mutation is centralized in transactional services. `StockPosition`, lots, reservations, purchase receipts, manufacturing orders/requirements and deliveries use row locks on critical transitions. Quantities are constrained non-negative in PostgreSQL and stock movements are immutable through a database trigger. Idempotency keys protect stock movement, reservation, material-consumption and return replay paths. Purchase receipt posting, manufacturing consumption, delivery completion and return application are designed so that a failure rolls back the surrounding transaction.

`ivadoo.api.tests_phase3_concurrency.Phase3ConcurrencyTests` exercises real PostgreSQL concurrency for reservations, transfers, purchase-receipt posting, manufacturing consumption, delivery completion and returns. It verifies single application/idempotence and final quantities. The transfer rollback case also verifies that an insufficient-stock failure does not leave a destination position behind.

## Approval and audit

Operational approval rules are scoped by organization/company/establishment/warehouse. Configured thresholds can require a distinct approver. Important stock, purchase, manufacturing, quality, delivery and approval transitions record append-only audit events with actor and relevant before/after state. Audit-event mutation remains blocked at both model and PostgreSQL levels.

## Review outcome

The Phase 3 gate requires the complete PostgreSQL CI suite to be green, including the concurrency suite and OpenAPI validation. No deployment automation or Phase 4+ capability is introduced by this review.
