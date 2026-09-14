# Phase 1 — Foundation backlog

Status: `active`.

The Phase 1 backlog is derived from the FashionERP specification and must not introduce Phase 2 business modules.

## Tracker

GitHub issue #9.

## Source rule

Before introducing or changing a technical choice, consult the FashionERP specification and the relevant uploaded/source files first.

- If a choice is explicitly defined in the sources, preserve it.
- If the sources do not define it, do not infer a replacement technology from another project, a CV, or developer familiarity.
- A choice explicitly confirmed by the FashionERP project owner becomes a project decision and must be documented as such.
- Genuinely new choices remain open until they become blocking and are explicitly validated.

## Validated implementation baseline

The FashionERP specification explicitly defines:

- PostgreSQL;
- REST `/api/v1`;
- OpenAPI;
- Control Plane / Data Plane separation;
- S3/MinIO-compatible object storage;
- Tauri + Owl/TypeScript for desktop;
- Docker as the supported direction for on-premise complexity.

Validated project implementation decisions:

- Django is the backend/server framework — ADR 0010;
- Django REST Framework is the REST layer — ADR 0011;
- drf-spectacular generates and validates the OpenAPI contract — ADR 0011;
- django-filter is the filtering helper for declared resource filters — ADR 0011.

Python 3.14 and Django 5.2 LTS are now the accepted runtime baseline — ADR 0012. Server dependencies may now be pinned and the first Django scaffold can be generated.

## Implementation order

### Gate 0 — backend decision completed

- #25 — completed: Django explicitly validated as the FashionERP backend framework.

### Gate 1 — REST/OpenAPI decision

- #30 — DRF + drf-spectacular accepted; conventions documented in `docs/api/README.md` and ADR 0011.
- #33 — completed: Python 3.14 + Django 5.2 LTS validated; dependency pinning/scaffolding is now unblocked.

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
