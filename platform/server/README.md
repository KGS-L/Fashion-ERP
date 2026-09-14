# FashionERP server

This directory contains the Django server runtime for the FashionERP platform.

Validated baseline:

- Python 3.14;
- Django 5.2 LTS;
- PostgreSQL;
- Django REST Framework;
- drf-spectacular;
- django-filter;
- Argon2id-preferred password hashing;
- opaque revocable server-side Bearer sessions for API authentication.

The business API is versioned under `/api/v1/`. OpenAPI is generated from the implemented API and exposed through the reserved schema/documentation routes.

## Authentication baseline

The Phase 1 authentication lifecycle is exposed under `/api/v1/auth/`.

Session policy defaults are environment-configurable:

- `FASHIONERP_SESSION_ABSOLUTE_TTL_SECONDS`: 30 days by default;
- `FASHIONERP_SESSION_IDLE_TTL_SECONDS`: 12 hours by default;
- `FASHIONERP_LOGIN_THROTTLE_RATE`: `10/min` by default.

These are implementation defaults, not immutable product rules. Production deployments must use HTTPS and must keep bearer tokens and secrets out of logs.

2FA, scoped RBAC and persistent security audit are completed by their dedicated Phase 1 issues.

Configuration is environment-driven. Production secrets must never be committed to the repository.
