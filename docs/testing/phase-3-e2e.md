# Phase 3 — operational end-to-end scenario

The Phase 3 acceptance journey is automated in `ivadoo.api.tests_phase3_e2e.Phase3OperationalJourneyTests`.

The scenario starts from a confirmed customer order and runs through a procurement receipt, incoming quality control, stock posting, material reservation, manufacturing consumption, finished-output posting, a blocking final-quality rework/reinspection cycle and a timestamped partial customer delivery. It asserts stock quantities at the receiving and finished-goods locations and checks that the order retains the correct remaining delivery balance.

This complements the domain suites for inventory, purchasing, manufacturing, quality and delivery. Those suites retain the negative, idempotency and isolation variants; the E2E test guards the integration points between modules without introducing a separate workflow engine or deployment dependency.
