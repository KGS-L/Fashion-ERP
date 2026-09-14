# Phase 1 — Foundation backlog

Status: `active`.

The Phase 1 backlog is derived from the FashionERP specification and must not introduce Phase 2 business modules.

## Tracker

GitHub issue #9.

## Source rule

Before introducing or changing a technical choice, consult the FashionERP specification and the relevant uploaded/source files first.

- If a choice is explicitly defined in the sources, preserve it.
- If the specification does not define a choice but the project already validated it separately, preserve that existing project decision and document the distinction.
- Genuinely new choices must not be inferred from familiarity; keep them open until they become blocking and are explicitly validated.
- Recommendations must be identified as recommendations, not as decisions from the specification.

## Validated implementation baseline

The specification explicitly defines PostgreSQL, REST `/api/v1`, OpenAPI, Control Plane/Data Plane, S3/MinIO and Tauri + Owl/TypeScript for desktop.

The project had separately validated the server baseline before Phase 1:

- Laravel 13;
- PHP 8.3+;
- Spatie Permission v8 as the RBAC dependency baseline.

This server decision is documented in `docs/adr/0010-laravel-server-baseline.md` and is not attributed to the specification itself.

## Implementation order

### Gate 0 — completed source verification

- #25 — completed: backend direction verified and preserved.
- #31 — completed: Laravel 13 / PHP 8.3+ runtime baseline documented.

### OpenAPI integration decision

- #30 — choose the concrete OpenAPI generation/validation integration without changing the accepted REST/OpenAPI requirement.

This is a new implementation detail and must follow the source-first rule before being fixed.

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
