# ADR 0010 — Laravel server baseline

Status: `accepted`

Decision owner: Phase 1 / issue #25.

## Context

The FashionERP specification defines the server constraints and product architecture, including PostgreSQL, REST `/api/v1`, OpenAPI, Control Plane / Data Plane separation, S3/MinIO-compatible object storage, strict tenant isolation and versioned migrations.

The specification itself does not name the server framework. Separately, the project had already validated the backend family before the Phase 1 implementation work: **Laravel 13 with PHP 8.3+**. That existing project decision is preserved here; it is not presented as a choice derived from the specification.

The previously validated authorization dependency is **Spatie Permission v8**, subject to the dependency-license review tracked by issue #28.

## Decision

FashionERP uses:

- **Laravel 13** as the primary server framework;
- **PHP 8.3+** as the server runtime baseline;
- **PostgreSQL** as the relational database, as required by the specification;
- **Spatie Permission v8** as the validated RBAC dependency baseline.

This ADR does not change the accepted FashionERP architecture. Control Plane and customer Data Plane remain separate architectural concerns, and each customer organization keeps the private ERP database boundary defined by the project specification.

## API constraints preserved

Laravel implementation must conform to the specification rather than redefine it:

- REST API under `/api/v1`;
- OpenAPI documentation;
- pagination, filters, sorting and search for applicable lists;
- authorization enforced at the API boundary;
- action endpoints only where required by business transitions;
- advanced API keys/webhooks remain an Enterprise Plus capability and are not confused with the base internal API.

## Security constraints preserved

The backend must implement and test:

- password hashing;
- revocable sessions;
- 2FA;
- RBAC with organization/company/establishment scopes and later warehouse scopes where applicable;
- immutable audit requirements for sensitive operations;
- strict inter-organization isolation;
- negative authorization and data-leakage tests;
- secrets outside source code.

Spatie Permission is an implementation aid for roles/permissions; it does not replace FashionERP's organization, company, establishment or tenant-isolation rules.

## Deployment constraints preserved

Laravel must remain compatible with the accepted deployment directions:

- managed cloud;
- customizable cloud;
- on-premise;
- private server;
- Docker-supported on-premise strategy;
- development, test, staging and production environments.

The accepted initial managed-cloud baseline remains OVHcloud VPS-2. No reverse proxy, queue backend, realtime technology or managed database product is selected by this ADR.

## Open points

The following implementation choices remain separate and must follow the source-first rule before being fixed:

- authentication/session implementation details;
- OpenAPI generation/validation tooling;
- HTTP runtime/process topology;
- queue implementation;
- realtime implementation;
- reverse proxy;
- final observability stack.

## Source-first rule

Before changing this baseline or introducing an additional foundational technology, consult the FashionERP specification and relevant project source files first. A recommendation must not be presented as an existing project decision unless it is supported by the sources or has been explicitly validated by the project owner.
