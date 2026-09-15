# Ivadoo server

This directory contains the Django server runtime for the Ivadoo platform.

The Python/Django package namespace is `ivadoo`. Django business application labels remain stable independently from the project package name so the migration graph and database table naming stay coherent.

Validated baseline:

- Python 3.14;
- Django 5.2 LTS;
- PostgreSQL;
- Django REST Framework;
- drf-spectacular;
- django-filter;
- Argon2id-preferred password hashing;
- opaque revocable server-side Bearer sessions for API authentication;
- TOTP two-factor authentication with encrypted secrets and one-time recovery codes.

The business API is versioned under `/api/v1/`. OpenAPI is generated from the implemented API and exposed through the reserved schema/documentation routes.

## Authentication baseline

The Phase 1 authentication lifecycle is exposed under `/api/v1/auth/`.

Session/security policy is environment-configurable through Ivadoo configuration keys:

- `IVADOO_SESSION_ABSOLUTE_TTL_SECONDS`: 30 days by default;
- `IVADOO_SESSION_IDLE_TTL_SECONDS`: 12 hours by default;
- `IVADOO_LOGIN_THROTTLE_RATE`: `10/min` by default;
- `IVADOO_2FA_ENCRYPTION_KEY`: required Fernet key used only to encrypt TOTP secrets;
- `IVADOO_TOTP_ISSUER`: authenticator issuer label, `Ivadoo` by default.

These are implementation defaults, not immutable product rules. Production deployments must use HTTPS and must keep bearer tokens and secrets out of logs.

2FA, scoped RBAC and persistent security audit are implemented by their dedicated Phase 1 issues.

Configuration is environment-driven. Production secrets must never be committed to the repository.

## Phase 1 review

The implemented Foundation behavior and final review checklist are documented in:

- `docs/foundation/README.md`;
- `docs/foundation/review-checklist.md`;
- `docs/security/foundation-exit-review.md`;
- `docs/compliance/THIRD_PARTY_NOTICES.md`;
- `docs/migrations/README.md`.

The Foundation established the platform primitives later phases build on. Production deployment automation remains outside the current test-only CI scope.
