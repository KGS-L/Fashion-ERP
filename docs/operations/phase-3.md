# Phase 3 — Operations

Phase 3 implements the operational chain defined by the Ivadoo roadmap: stock, purchasing, simple production, quality and delivery. It remains server-side/API functionality; no Phase 4 mobile/employee/CRM capability and no Phase 5 accounting/BI capability is presented as available here.

## Inventory

Warehouses belong to an organization/company and may be attached to an establishment. Stock locations are hierarchical inside a warehouse. Physical quantities are represented by `StockPosition`; lots/rolls/remnants provide traceability. Movements are append-only and cover receipts, issues, transfers, adjustments, production consumption/output, damage and returns. Reservations move quantity from available to reserved/in-production states without allowing negative balances.

Critical invariant: clients never write stock quantities directly. Every quantity change passes through transactional services using row locks and immutable stock movements.

## Purchasing

Supplier records support contacts, addresses and product links. The procurement flow covers purchase requests, RFQs, supplier quotations/comparison and purchase orders with controlled transitions. Receipts may be partial; each receipt line is controlled into accepted/rejected quantities before posting. Only accepted quantity enters stock, and posted supplier history remains traceable.

Operational approval rules can protect purchase-order approval above configured thresholds and can require a distinct approver.

## Manufacturing

Operational BOM versions snapshot material requirements into manufacturing orders. A manufacturing order moves through draft → ready → in progress → done, with cancellation only where allowed. Material reservation and consumption are coupled to inventory; supplemental consumption requires an explicit reason. Reusable remnants, scrap/loss and material variance are tracked. Completion creates one finished-output stock receipt and refuses unresolved material reservations.

Simple work-center operations cover the Phase 3 cutting/sewing/finishing flow. Advanced capacity/load planning remains Phase 5 (#136).

## Quality

Inspections cover receiving, in-process and final contexts. Criteria and defects are frozen when an inspection is completed. A blocking reject/rework prevents dependent operational progress until a compliant reinspection exists. Rework instructions and completion are explicit and audited. Advanced quality analytics remain a later phase.

## Delivery, partial delivery and returns

Deliveries allocate order-line quantities against quality-approved finished output. Preparation requires packages. Local delivery uses prepared → assigned → shipped → delivered; pickup uses prepared → ready-for-pickup → picked-up. Terminal completion requires timestamped proof and issues finished stock exactly once. Partial deliveries preserve the remaining order balance. Returns/exchanges trace back to the original delivery issue movement and support restock, quarantine or damaged dispositions.

Customer fittings/alterations/customer validation from #153 participate in delivery readiness where configured.

## RBAC and API

All resources are exposed under `/api/v1`. Phase 3 permissions are explicit for inventory, purchase, manufacturing, quality, delivery and operational approval domains. Important actions are represented as action endpoints/services rather than arbitrary status mutation. The generated OpenAPI schema is validated warning-free by CI.

## Reproducible acceptance journey

`ivadoo.api.tests_phase3_e2e.Phase3OperationalJourneyTests` starts from a confirmed customer order and covers required procurement/receipt, incoming quality, stock, reservation, manufacturing consumption/output, final-quality rework/reinspection and a partial customer delivery with proof and remaining balance. Domain suites separately cover purchase-request/RFQ/PO transitions, negative cases, returns/exchanges, scope isolation and idempotency.

## Explicitly deferred

Phase 3 does not implement the generic Workflow Engine (#146), multichannel notifications, employee/mobile workflows, CRM pipeline, advanced MRP capacity planning, accounting/consolidation/BI, deployment packaging, Tauri desktop implementation or production backup automation. Those remain assigned to their existing later-phase issues.
