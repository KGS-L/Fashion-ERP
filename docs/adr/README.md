# Architecture Decision Records

Architecture Decision Records (ADRs) document important technical decisions made during FashionERP development.

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
- `0010-django-server-baseline.md` — Django as the explicitly validated FashionERP backend/server framework.

Decisions that remain open in the functional and technical specification must not be presented as finalized ADRs until explicitly validated.

Before introducing or changing a technical decision, the project specification and relevant source files must be reviewed first. A technology must not be treated as a FashionERP decision merely because it is used in another project or appears in the project owner's general toolset.
