# Phase 1 Foundation security exit review

Review scope: Phase 1 Foundation branch `phase/1-foundation`.

## Result

No known blocker was identified in the implemented Foundation security boundary at the time of this review.

The review covers the application and CI artifacts in this repository. It does not claim that an undeployed production infrastructure has been penetration-tested.

## Tenant isolation

Implemented controls:

- one customer Organization per private Data Plane PostgreSQL database;
- no request header/parameter that selects an arbitrary customer database;
- Company and Establishment resources are scoped inside the local Organization;
- scoped RBAC filters resources server-side;
- out-of-scope object lookups use 404 where appropriate.

Automated evidence includes:

- primary vs isolated tenant database migration/tests;
- cross-database reference-data isolation;
- Company vs Establishment scope tests;
- inter-Establishment denial;
- permission revocation effective on the next request.

## Authentication and sessions

Implemented controls:

- Argon2-preferred Django password hashing;
- opaque random Bearer tokens with only token digests stored;
- absolute and idle expiration;
- explicit session revocation;
- own-device/session listing and revocation;
- TOTP 2FA with encrypted secret at rest;
- one-time recovery codes stored only as digests;
- other sessions revoked after security-sensitive 2FA state changes;
- login throttling.

Raw passwords, Bearer tokens, TOTP secrets and recovery codes are excluded from audit snapshots.

## Authorization

Business API access is deny-by-default.

Ivadoo scoped RBAC is independent from Django's `is_superuser` flag for business authorization.

Effective access is resolved server-side from current PostgreSQL grants/roles/permissions rather than long-lived authorization claims in Bearer tokens.

Automated tests cover direct grants, group grants, Company scope, Establishment scope, revocation and absence of superuser bypass.

## Audit

Sensitive Foundation changes are written to an append-only audit journal.

Immutability is enforced by:

- no REST write API;
- Django model update/delete rejection;
- PostgreSQL trigger rejecting UPDATE/DELETE.

Audit tests verify actor/scope/before/after data and secret exclusion.

## Internationalization security boundary

User/Company/Establishment locale settings are validated and scoped.

Country fiscal/accounting rules are not silently embedded in the common core.

## Secrets review

Repository searches performed during the exit review found no committed patterns for:

- private-key PEM blocks;
- AWS access keys beginning with `AKIA`;
- GitHub personal access tokens;
- common live payment/API secret prefixes.

Production-sensitive values are environment-driven, including:

- Django secret key;
- PostgreSQL password;
- TOTP encryption key.

Known fixed credentials in CI/reference data are explicitly test-only and must not be reused outside local/CI validation.

The repository ignores local `.env`, private key and certificate artifacts.

CI also performs a lightweight high-risk secret-pattern scan on tracked files.

## CI permissions and deployment boundary

GitHub Actions workflows use read-only repository contents permission for the current test jobs.

The Phase 1 CI:

- validates repository structure;
- validates migrations and PostgreSQL;
- validates OpenAPI;
- runs Django integration/security tests;
- scans for selected high-risk secret formats.

It does not deploy, publish a production image, provision production infrastructure or require production secrets.

## Residual/non-blocking items

The following remain outside the implemented Phase 1 application boundary and must not be represented as completed production controls:

- production TLS/reverse-proxy hardening;
- production PostgreSQL version and HA topology;
- automated backup/restore infrastructure and scheduled restoration drills;
- production secret manager and key-rotation runbooks;
- TOTP encryption-key rotation procedure;
- audit retention/legal-hold policy;
- S3/MinIO object storage until a module consumes it;
- Enterprise Plus SSO, API keys and webhooks;
- external penetration testing.

These items are either deployment/operations responsibilities or explicitly deferred product capabilities.

## Exit assessment

For the Phase 1 Foundation application scope:

- no known inter-tenant data leak is present in the tested paths;
- no production secret is known to be committed;
- required negative authorization/isolation tests are present and green;
- security-sensitive operations are auditable;
- remaining gaps are documented rather than presented as implemented.
