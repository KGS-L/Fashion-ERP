# Phase 0 — Framing

Phase 0 establishes the decisions and acceptance baseline required before implementation of the FashionERP foundation begins.

## Branch

`phase/0-framing`

## Tracking

Global tracker: #6

Phase issues:

- #1 — product, editions and license decisions;
- #2 — architecture and deployment baseline;
- #3 — first pilot and acceptance criteria;
- #4 — architecture decision records;
- #5 — Phase 1 backlog preparation;
- #7 — first country localization and initial support model.

## Objectives

- confirm the product scope and edition boundaries;
- record unresolved architectural and product decisions;
- define the first pilot scope and acceptance criteria;
- confirm repository, branch and CI conventions;
- prepare the transition to Phase 1 — Foundation.

## Decisions to close

The functional and technical specification still leaves several framing decisions open. Phase 0 must explicitly confirm or defer them, including:

- final product naming and branding status;
- exact licensing boundaries between Community and commercial components;
- supported operating systems and minimum versions for installable applications;
- first country localization to implement;
- initial usage or edition limits where applicable;
- initial managed-cloud assumptions;
- support model and pilot conditions.

## Architecture baseline

Phase 0 must preserve the architecture already defined by the specification:

- separation between Control Plane and Data Plane;
- private ERP data boundary per customer organization;
- PostgreSQL for ERP data;
- S3/MinIO-compatible document storage;
- REST/OpenAPI interfaces;
- Tauri + Owl/TypeScript for the desktop application;
- supported managed cloud, customizable cloud, on-premise and private-server deployment modes.

No new implementation technology should be introduced during Phase 0 without an explicit architecture decision.

## Exit criteria

Phase 0 is complete when:

- open framing decisions are documented as accepted, deferred or rejected;
- the first pilot scope is documented;
- Phase 1 scope is unambiguous;
- relevant architecture decisions are recorded;
- GitHub issues for Phase 1 can be created from an agreed baseline;
- repository CI remains test-only with no deployment automation.
