# Phase 1 — Foundation backlog

Status: `active`.

The Phase 1 backlog is derived from the FashionERP specification and must not introduce Phase 2 business modules.

## Tracker

GitHub issue #9.

## Source rule

Before introducing or changing a technical choice, consult the FashionERP specification and the relevant uploaded/source files first.

- If a choice is explicitly defined in the sources, preserve it.
- If the sources do not define it, do not infer a replacement technology from another project, a CV, or developer familiarity.
- Genuinely new choices remain open until they become blocking and are explicitly validated.
- Recommendations must be identified as recommendations, not as project decisions.

## Validated implementation baseline

The FashionERP specification explicitly defines:

- PostgreSQL;
- REST `/api/v1`;
- OpenAPI;
- Control Plane / Data Plane separation;
- S3/MinIO-compatible object storage;
- Tauri + Owl/TypeScript for desktop;
- Docker as the supported direction for on-premise complexity.

The current FashionERP sources available to the project do **not** identify Laravel, NestJS, Django, FastAPI, Odoo/Python or another server framework as an accepted backend implementation choice. Therefore the server framework remains open until explicitly validated.

## Implementation order

### Gate 0 — backend decision

- #25 — verify and explicitly validate the server/backend framework before server-side implementation begins.

### OpenAPI integration decision

- #30 — choose the concrete OpenAPI generation/validation integration only after the server framework is actually validated.

### Foundation sequence

1. #10 — authentication and session lifecycle
2. #11 — organizations and isolation
3. #12 — companies and establishments hierarchy/scopes
4. #13 — users, groups, roles and permissions
5. #14 — audit and traceability
6. #15 — base internationalization
7. #18 — 2FA and device/session management
8. #19 — Foundation REST/OpenAPI conventions
9. #20 — versioned Foundation migrations
10. #21 — PostgreSQL/test storage support
11. #17 — reproducible Foundation reference data
12. #16 — integration, authorization and isolation tests
13. #22 — security exit review
14. #23 — Foundation documentation/review preparation
15. #27 — implementation CI checks as test tooling becomes available
16. #28 — dependency-license compliance review
17. #24 — Phase 1 exit gate and PR to `main`

## Deferred/non-blocking technology decision

- #26 records that the mobile framework is still intentionally open. It becomes blocking before real implementation of the workshop or public/client mobile applications, not before the server/core Foundation work.

## Required cross-cutting tests

Phase 1 is not accepted without tests for:

- unauthenticated access;
- revoked sessions;
- inter-organization isolation;
- company/establishment scopes;
- role and permission enforcement at the API boundary;
- audit events for sensitive Foundation operations;
- i18n configuration/format behavior;
- migrations against PostgreSQL;
- negative access scenarios that demonstrate absence of data leakage.

## Branch rule

The branch `phase/1-foundation` was created from updated `main` after Phase 0 was reviewed and merged.

CI remains validation/test-only; deployment automation is outside this backlog.
