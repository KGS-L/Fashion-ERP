# Phase 3 — operational end-to-end scenario

The Phase 3 acceptance journey is automated in `ivadoo.api.tests_phase3_e2e.Phase3OperationalJourneyTests`.

The scenario starts from a confirmed customer order with no material stock. It creates and approves a purchase request linked to that order, sends an RFQ, records and selects a supplier quotation, then creates and transitions the purchase order. The receipt is subjected to incoming quality control before accepted quantity is posted to stock.

The same trace then reserves material for the linked manufacturing order, consumes it, posts finished output, records a blocking final-quality defect, executes rework and a successful reinspection, then performs a customer fitting that requests an alteration. The alteration is completed, a second fitting is accepted by the customer, and delivery readiness is restored.

Finally, one unit of a two-unit customer order is prepared, assigned, shipped and delivered with timestamped proof. The test asserts the remaining order delivery balance and the final stock quantity.

This integrated test complements the domain suites for inventory, purchasing, manufacturing, quality, fittings/alterations and delivery. Those suites retain negative, scope-isolation, idempotency, return/exchange and concurrency variants. The E2E journey verifies module integration without introducing a generic workflow engine, Phase 4 functionality or deployment dependency.
