# Phase 3 — REST/API operations contract

This document records the consolidated server contract for the Phase 3 operational perimeter. The canonical API remains versioned below `/api/v1`; generated OpenAPI is validated by CI with `drf-spectacular --validate --fail-on-warn`.

## Resource families

| Domain | API root | Main business actions |
| --- | --- | --- |
| Inventory | `/api/v1/inventory/` | movements, reservations, reservation lifecycle |
| Purchasing | `/api/v1/purchases/` | request/RFQ/order transitions, supplier selection, receipts |
| Manufacturing | `/api/v1/manufacturing/` | BOM/order transitions, material reservation/consumption, operations, completion |
| Quality | `/api/v1/quality/` | inspections, completion, defects/rework and quality summaries |
| Delivery | `/api/v1/delivery/` | preparation/assignment/shipping/completion, partial balances, returns/exchanges |
| Operational approvals | `/api/v1/operations/` | approval-rule management, stock approval request/decision |

State-changing business transitions are exposed as explicit actions rather than direct writes to protected state fields. Representative serializers expose lifecycle state and approval timestamps as read-only fields; views additionally reject direct edits once a resource leaves the editable state.

## Authorization and scopes

Every operational queryset starts from the authenticated user's organization and is narrowed with scoped RBAC through `authorized_company_ids` and `has_permission`. Mutations re-check the effective company/site context before invoking domain services. Warehouse-backed operations also validate establishment and warehouse ownership. Object identifiers from another organization or company therefore do not widen access.

Phase 3 permissions are explicitly seeded for `inventory`, `purchase`, `manufacturing`, `quality`, `delivery` and `operations`. Operational approval rules can be scoped at organization, company, establishment and warehouse levels and may require a distinct approver.

## Integrity, audit and extensibility boundaries

Important transitions and mutations call the append-only audit service with actor, object and before/after state. Stock movements are immutable at PostgreSQL level and inventory mutations use transactional domain services, row locks and idempotency keys. Imports or future metadata/custom-field extensions must enter through the same serializers/services; Phase 3 does not introduce a raw import path capable of bypassing domain validation.

The generic configurable Workflow Engine remains outside this issue and is tracked separately. Phase 3 implements only the explicit operational state machines and approval thresholds required by the cahier des charges.

## Verification

The backend CI executes Django system checks, `makemigrations --check --dry-run`, migration application on both the primary and isolated tenant databases, OpenAPI validation and the complete Django test suite. `ivadoo.api.tests_phase3_contracts` adds a consolidated guard for route registration, authentication, seeded Phase 3 RBAC modules and non-writable purchase-order lifecycle fields. Domain test suites continue to cover positive/negative mutations, scope isolation, audit, idempotency and protected transitions.
