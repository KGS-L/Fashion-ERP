# Phase 1 Foundation review checklist

This checklist prepares the `phase/1-foundation` branch for the final gate and pull request to `main`.

## Implemented Foundation scope

- [x] Django/Python runtime baseline
- [x] REST/OpenAPI baseline under `/api/v1`
- [x] authentication and revocable sessions
- [x] Organization private Data Plane boundary
- [x] Company / Establishment hierarchy
- [x] scoped users/groups/roles/permissions
- [x] immutable audit journal
- [x] base internationalization
- [x] TOTP 2FA and device/session management
- [x] versioned Foundation migrations
- [x] PostgreSQL test baseline
- [x] reproducible synthetic reference data
- [x] integration/authorization/isolation tests
- [x] Foundation security exit review
- [x] direct dependency-license review

## API and data boundaries

- [x] Foundation paths represented in OpenAPI
- [x] OpenAPI validation fails on warnings
- [x] Phase 2 business routes absent
- [x] Enterprise Plus API keys/webhooks absent
- [x] one Organization per private Data Plane database
- [x] Company/Establishment scoping enforced server-side
- [x] out-of-scope detail access does not leak resource existence

## Security evidence

- [x] Argon2-preferred password hashing
- [x] opaque Bearer tokens stored only as digests
- [x] session expiry/revocation tests
- [x] TOTP secret encrypted at rest
- [x] recovery codes stored only as digests
- [x] deny-by-default RBAC
- [x] permission revocation effective on next request
- [x] no business authorization bypass via Django superuser
- [x] append-only audit protected by PostgreSQL
- [x] selected high-risk secret-pattern scan in CI
- [x] negative isolation/access tests

## Migration/test evidence

- [x] model/migration drift check
- [x] migration graph conflict check
- [x] migration plan generated in CI
- [x] empty primary PostgreSQL database migrates successfully
- [x] isolated tenant PostgreSQL database migrates successfully
- [x] no unapplied migrations after migration
- [x] full Django test suite in CI
- [x] repository structure/documentation tests in CI

## Documentation

- [x] architecture decisions under `docs/adr/`
- [x] API contract under `docs/api/`
- [x] migration/recovery procedure under `docs/migrations/`
- [x] test/reference-data documentation under `docs/testing/`
- [x] security exit review under `docs/security/`
- [x] dependency compliance/notices under `docs/compliance/`
- [x] implemented Foundation summary under `docs/foundation/`

## Explicitly deferred

The following are not Phase 1 implemented capabilities:

- CRM/customer business workflows
- measurements
- products/materials/variants
- orders/sales
- inventory/warehouses
- purchasing
- manufacturing
- deliveries/returns
- finance/accounting
- reporting/BI
- country fiscal/accounting localization
- Enterprise Plus SSO
- public API keys
- webhooks
- object storage until a consuming module exists
- production infrastructure/deployment automation
- production backup automation/restoration drills
- external penetration testing

## Final gate

The pull request to `main` is ready to be opened because:

- [x] all mandatory Phase 1 implementation issues are closed;
- [x] #16 integration/isolation tests are green;
- [x] #22 security review is closed;
- [x] #27 CI checks are closed/green;
- [x] #28 dependency compliance is closed;
- [x] latest branch Backend Tests are green;
- [x] latest branch Repository Tests are green;
- [x] no Phase 2 functionality has been introduced early.

Opening the pull request does not itself authorize merging it. Merge remains a review decision.
