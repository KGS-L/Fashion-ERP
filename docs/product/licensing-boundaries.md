# Ivadoo open-core licensing boundaries

Status: accepted hardening rule before Phase 4.

Ivadoo uses the open-core model defined by the product specification: Community is the open core, while Business, Enterprise Plus and explicitly premium components use separate commercial terms.

## Authoritative technical boundary

The machine-readable source of truth is `docs/product/component-license-map.json`.

The repository root `LICENSE` defines the default license as `LGPL-3.0-only`. A component changes away from that default only when it is explicitly classified by one of these mechanisms:

- a local `LICENSE` file for an entire commercial directory;
- a file-level `SPDX-License-Identifier: LicenseRef-Ivadoo-Commercial` marker for a commercial file inside a mixed Community/commercial package;
- the matching entry in `component-license-map.json`.

Commercial terms are described by `LICENSE-COMMERCIAL`.

## Current Phase 0–3 boundary

Community currently covers the platform/Foundation and the Phase 2 core needed for the Community edition: identity, organizations, authorization, audit, internationalization, customers, measurements, articles/models/basic catalogue and simple custom orders.

The operational capabilities introduced in Phase 3 are Business scope: inventory, purchasing, simple manufacturing, basic quality, delivery and operational approvals. Enterprise Plus adds advanced quality later; it does not make the basic Phase 3 quality workflow Community.

The `sales` package is intentionally mixed. Core quotation/order files remain under the repository default Community license, while fitting, alteration and customer-validation implementation files introduced with the Phase 3 operational workflow are classified as Business using file-level SPDX markers.

## Merge rule for new code

Before merging any future Business or Enterprise Plus runtime code, the contributor must classify it in `component-license-map.json` and add the corresponding local or file-level commercial marker. Community code remains under the root default license unless explicitly changed by a future product decision.

The automated backend test `test_component_license_boundaries.py` verifies that every path classified as commercial exists and carries the expected marker.

This file documents the repository boundary only. Customer-facing legal terms may require separate legal review before commercial distribution.
