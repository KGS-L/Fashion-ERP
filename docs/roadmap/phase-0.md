# Phase 0 — Framing

Phase 0 establishes the decisions and acceptance baseline required before implementation of the FashionERP foundation begins.

## Branch

`phase/0-framing`

## Tracking

Global tracker: #6

Phase issues:

- [x] #1 — product, editions and license decisions;
- [x] #2 — architecture and deployment baseline;
- [x] #3 — first pilot and acceptance criteria;
- [x] #4 — architecture decision records;
- [x] #5 — Phase 1 backlog preparation;
- [x] #7 — first country localization and initial support model;
- [x] #8 — managed cloud provider and cost strategy.

## Objectives

- confirm the product scope and edition boundaries;
- record unresolved architectural and product decisions;
- define the first pilot scope and acceptance criteria;
- confirm repository, branch and CI conventions;
- prepare the transition to Phase 1 — Foundation.

## Decisions closed

- FashionERP is the definitive product name;
- Community core license: LGPL-3.0-only;
- commercial licensing remains separate for Business, Enterprise Plus and premium components;
- edition usage limits are documented;
- architecture baseline is accepted;
- desktop OS baseline is Windows 11, macOS 14+ and Ubuntu 24.04 LTS+;
- first-pilot reference scenario is documented;
- structural ADRs are accepted;
- Burkina Faso is the first country localization, with OHADA/SYSCOHADA as the accounting foundation and country-specific rules kept outside the common ERP core;
- official pilot support uses email and private ticketing, with WhatsApp only as a complementary coordination channel;
- OVHcloud VPS-2 is the initial managed-cloud baseline for pilot and early small managed-cloud customers;
- PostgreSQL remains self-managed initially in the isolated customer environment, with S3-compatible object storage and independent application-level backup retention;
- Phase 1 backlog is prepared.

## Architecture baseline

Phase 0 preserves the architecture defined by the specification:

- separation between Control Plane and Data Plane;
- private ERP data boundary per customer organization;
- PostgreSQL for ERP data;
- S3/MinIO-compatible document storage;
- REST/OpenAPI interfaces;
- Tauri + Owl/TypeScript for the desktop application;
- managed cloud, customizable cloud, on-premise and private-server deployment modes.

No new implementation technology is introduced as accepted without an explicit decision. The main server framework and mobile framework therefore remain open and are tracked for later decision before their implementation becomes necessary.

## Exit criteria

Phase 0 is complete when:

- framing decisions are documented as accepted, deferred or rejected;
- the first pilot scope is documented;
- Phase 1 scope is unambiguous;
- relevant architecture decisions are recorded;
- GitHub issues for Phase 1 are ready from an agreed baseline;
- repository CI remains test-only with no deployment automation;
- relevant CI checks are green before the Phase 0 PR is considered ready.

At the end of Phase 0, all framing issues listed above are resolved. The branch is ready for final CI verification and pull-request review before merge into `main`.
