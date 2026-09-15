# Architecture Decision Records

Architecture Decision Records (ADRs) document important technical and product-architecture decisions made during Ivadoo development.

Each ADR records context, decision, consequences, status and relevant alternatives or deferred choices.

## Accepted ADRs

- `0001-control-plane-data-plane.md` — separate Control Plane and Data Plane;
- `0002-private-erp-database-per-organization.md` — private ERP database boundary per customer organization;
- `0003-postgresql.md` — PostgreSQL as the primary relational database;
- `0004-s3-minio-object-storage.md` — S3/MinIO-compatible object storage for business files;
- `0005-rest-openapi.md` — versioned REST API documented with OpenAPI;
- `0006-tauri-owl-desktop.md` — Tauri + Owl/TypeScript desktop application;
- `0007-modularity-and-country-localizations.md` — modular domains with country localizations separated from the common ERP core;
- `0008-ci-test-only.md` — GitHub Actions CI limited to validation and tests;
- `0009-ovh-vps2-initial-managed-cloud.md` — OVHcloud VPS-2 as the accepted initial managed-cloud baseline for pilot and early small customers;
- `0010-django-server-baseline.md` — Django as the explicitly validated backend/server framework;
- `0011-drf-drf-spectacular.md` — Django REST Framework + drf-spectacular as the accepted REST/OpenAPI implementation baseline;
- `0012-python314-django52-lts.md` — Python 3.14 + Django 5.2 LTS as the accepted server runtime baseline;
- `0013-api-auth-revocable-sessions.md` — opaque revocable server-side Bearer sessions as the accepted API authentication baseline;
- `0014-one-organization-per-data-plane-database.md` — one customer organization per private ERP Data Plane database, with a local Organization root;
- `0015-scoped-rbac-role-grants.md` — deny-by-default RBAC using roles, groups and Organization/Company/Establishment grants;
- `0016-append-only-postgresql-audit-journal.md` — append-only PostgreSQL audit events for sensitive Foundation operations;
- `0017-foundation-internationalization-boundary.md` — five-language Foundation catalogs, locale preferences, currencies, dated rates, timezones and configurable units without country fiscal rules;
- `0018-totp-two-factor-authentication.md` — TOTP 2FA, encrypted enrollment secrets, one-time recovery codes and secure administrator reset;
- `0019-module-registry-and-runtime-capability-gates.md` — static code manifests plus organization-local activation state and server-side API capability gates;
- `0020-hybrid-custom-fields-sidecar-storage.md` — strongly typed core fields plus versioned custom-field metadata and sidecar JSONB values;
- `0021-metadata-api-from-authoritative-model-registry.md` — runtime metadata derived from code manifests, Django fields, organization custom fields and RBAC;
- `0022-customization-security-boundary.md` — deny-by-default customization with protected native invariants and layered field permissions;
- `0023-generic-tabular-data-import-export.md` — CSV/XLSX import/export through explicitly registered, scoped domain adapters;
- `0024-ivadoo-product-brand-and-technical-namespace.md` — Ivadoo as the definitive product identity, including the `ivadoo` Python namespace and `IVADOO_*` configuration namespace;
- `0025-shared-owl-web-and-tauri-frontend.md` — one primary Owl/TypeScript ERP frontend shared by browser and Tauri, with explicit native adapters and separate public/client security boundaries.

Decisions that remain open in the functional and technical specification must not be presented as finalized ADRs until explicitly validated.

Before introducing or changing a technical decision, the project specification and relevant source files must be reviewed first. A technology must not be treated as an Ivadoo decision merely because it is used in another project or appears in the project owner's general toolset.
