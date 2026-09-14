# Phase 1 — Foundation backlog

Status: `prepared` during Phase 0.

The Phase 1 backlog is derived from the FashionERP specification and must not introduce Phase 2 business modules.

## Tracker

GitHub issue #9.

## Implementation order

### Gate 0 — implementation technology decision

- #25 — define the server framework before server-side implementation begins.

This is intentionally separate because the specification does not name the main server framework.

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

The branch `phase/1-foundation` is created from updated `main` only after Phase 0 has been reviewed and merged.

CI remains validation/test-only; deployment automation is outside this backlog.
