# Phase 1 — Foundation implementation summary

Status: implementation complete on `phase/1-foundation`, pending final exit gate / PR review.

This document summarizes what the Phase 1 Foundation actually implements. It intentionally excludes Phase 2 business modules and deferred Enterprise Plus capabilities.

## Runtime and API

Validated server baseline:

- Python 3.14;
- Django 5.2 LTS;
- Django REST Framework;
- drf-spectacular;
- django-filter;
- PostgreSQL.

The internal REST API is versioned under `/api/v1/`.

OpenAPI is generated from the implemented routes and validated in CI with warnings treated as failures.

## Tenant and organization boundary

The Foundation uses one customer Organization per private Data Plane PostgreSQL database.

Inside that database:

`Organization -> Company -> Establishment`

One Organization may contain multiple Companies, and each Company may contain multiple Establishments.

The API does not expose a request header or parameter that selects another customer database.

## Identity and security

Implemented:

- UUID user model;
- Argon2-preferred password hashing;
- opaque server-side Bearer sessions;
- absolute and idle session expiry;
- session/device listing and revocation;
- TOTP 2FA;
- encrypted TOTP secrets;
- one-time recovery codes stored only as digests;
- administrator-assisted 2FA reset with RBAC and reauthentication;
- login throttling.

Not implemented in Phase 1:

- Enterprise SSO;
- passkeys/WebAuthn;
- SMS/email recovery channel;
- public API keys.

## Scoped RBAC

Ivadoo business authorization is deny-by-default and independent from Django's global superuser semantics.

The authorization model is:

`Permission -> Role -> AccessGrant -> User | AccessGroup`

Grant scopes currently supported:

- Organization;
- Company;
- Establishment.

Effective permissions are resolved from PostgreSQL on each request, so revocation is effective on the next request.

## Audit

Sensitive Foundation operations are written to an append-only PostgreSQL audit journal.

Events record actor, time, object, result and allow-listed before/after values when relevant.

Update/delete of audit events is blocked both at the Django model boundary and by a PostgreSQL trigger.

## Internationalization

Initial supported languages:

- French;
- English;
- Spanish;
- Portuguese;
- Arabic.

The Foundation includes:

- stable-key translation catalogs;
- plural handling;
- RTL direction for Arabic;
- user language preference;
- Company language default;
- Company functional currency reference;
- dated Organization-scoped exchange rates;
- Establishment IANA timezone;
- configurable units of measure.

Country tax/accounting localization is deliberately outside the common Foundation core.

## REST/OpenAPI contract

Current Foundation namespaces:

- `/api/v1/auth/`;
- `/api/v1/organizations/`;
- `/api/v1/companies/`;
- `/api/v1/establishments/`;
- `/api/v1/access/`;
- `/api/v1/audit/`;
- `/api/v1/i18n/`.

Phase 2 business namespaces are intentionally absent.

Webhooks and API keys are also absent because the specification reserves them for Enterprise Plus.

## Migrations and PostgreSQL

All Foundation schema changes are versioned as Django migrations.

CI verifies:

- no model/migration drift;
- linear/non-conflicting Foundation migration graph;
- migration plan generation;
- forward migration from an empty PostgreSQL database;
- the same migration graph on an isolated tenant database;
- no unapplied migrations after migration.

Rollback/restore procedures are documented under `docs/migrations/`.

## Reference data and integration tests

A deterministic synthetic reference dataset is available through:

`python manage.py seed_foundation_reference`

It provides:

- a pilot Organization with one Company and two Establishments;
- users with different RBAC scopes;
- language/currency/timezone/unit configuration;
- a second Organization in an isolated database for isolation tests.

No real personal data is required.

Integration tests cover authorized flows, denied flows, inter-Organization isolation, inter-Establishment isolation, permission revocation and audit behavior.

## CI boundary

Phase 1 CI is validation/test-only.

It currently checks:

- repository/documentation structure;
- selected high-risk secret patterns;
- Django system checks;
- migration drift and migration plan;
- PostgreSQL migrations on primary and isolated tenant databases;
- OpenAPI validity with zero warnings;
- full Django test suite.

It does not deploy, publish a production release or provision production infrastructure.

## Security review

The Phase 1 application security exit review is recorded in:

`docs/security/foundation-exit-review.md`

No known application-level blocker is recorded for the implemented Foundation scope.

Production infrastructure hardening, external penetration testing, backup automation, secret-management operations and other deployment concerns remain separate responsibilities.

## Deferred to later phases

Phase 1 does not implement the business modules for:

- CRM/customers;
- measurements;
- products/materials/variants;
- sales/orders;
- inventory/warehouses;
- purchasing;
- manufacturing;
- delivery/returns;
- finance/accounting;
- reporting/BI.

The Foundation provides the security, organization, API, audit and internationalization primitives those modules will build on.
