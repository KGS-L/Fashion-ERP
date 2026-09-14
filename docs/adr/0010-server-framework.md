# ADR 0010 — Server framework

Status: `proposed`

Decision owner: Phase 1 / issue #25.

## Context

The FashionERP specification fixes the main server constraints but does not select the application framework.

The server must support:

- PostgreSQL as the primary relational database;
- REST endpoints versioned under `/api/v1`;
- OpenAPI documentation;
- authentication, revocable sessions, 2FA and RBAC with organization/company/establishment scopes;
- versioned database migrations;
- strict tenant isolation and authorization tests;
- background tasks, notifications and document storage;
- S3/MinIO-compatible file storage;
- managed cloud, customizable cloud, on-premise and private-server deployments;
- a modular open-core product model.

The framework choice must reduce infrastructure fragmentation while keeping business modules isolated and testable.

## Proposed decision

Use **Laravel 13.x** as the primary FashionERP server framework.

Laravel 13 requires PHP 8.3 or later. The exact production PHP baseline remains a separate runtime decision.

FashionERP should initially be implemented as a **modular monolith**, not as a collection of microservices. Business domains remain isolated by module boundaries while sharing one application runtime and the customer ERP database defined by the architecture.

The Control Plane and customer Data Plane remain architecturally separate even if both eventually use Laravel.

## Why Laravel is proposed

Laravel provides a cohesive baseline for the needs of a domain-heavy ERP:

- first-party database access and versioned migrations with PostgreSQL support;
- authorization through gates and policies, suitable as a foundation for scoped RBAC;
- validation, middleware, API resources and HTTP routing for REST endpoints;
- queues and scheduled jobs for asynchronous operations;
- notifications and mail primitives;
- filesystem abstraction with S3-compatible storage support;
- mature testing support;
- Composer packages and application modules suitable for an open-core product where Community and commercial capabilities must remain separable.

This reduces the number of foundational libraries that must be chosen independently before Phase 1 can start.

## Important consequence: OpenAPI

Laravel does not make the FashionERP OpenAPI requirement disappear.

A dedicated OpenAPI generation and validation strategy must be chosen separately and must be enforced in CI so that the API contract does not drift from the implementation. This is tracked in issue #30 and should be coordinated with issue #19.

## Security consequences

Laravel authorization primitives are only a foundation. FashionERP must still implement and test its own domain rules for:

- organization isolation;
- company and establishment scopes;
- warehouse scopes when applicable;
- module/action permissions;
- sensitive measurements, photos, financial operations and documents;
- session revocation and 2FA;
- immutable audit requirements.

No implicit Eloquent query convention is sufficient by itself to prove tenant isolation. Integration and security tests remain mandatory.

## Deployment consequences

Laravel is compatible with the accepted Docker-based deployment direction and can run on the initial OVHcloud VPS-2 baseline.

The exact production HTTP runtime, reverse proxy and process topology are intentionally not selected by this ADR. They will be decided when deployment implementation requires them.

## Alternatives considered

### NestJS 11

Strengths:

- TypeScript across the server codebase;
- first-class module structure;
- official OpenAPI integration;
- guards and metadata are a strong fit for authorization;
- good testing and dependency-injection model.

Reason not currently preferred:

A complete ERP baseline would still require several additional foundational choices such as ORM/migration strategy, storage integration, queue implementation and associated conventions. It is viable, but produces more early platform decisions than Laravel for the same Phase 1 scope.

### Django 6 + Django REST Framework

Strengths:

- mature ORM and migrations;
- strong PostgreSQL support;
- mature authentication and administration tooling;
- proven modular application structure.

Reason not currently preferred:

REST/OpenAPI would rely on additional framework/packages and there is no clear project-specific advantage over Laravel that compensates for changing the server ecosystem.

### FastAPI

Strengths:

- excellent OpenAPI integration;
- strong typing and validation;
- well suited to focused APIs and Python services.

Reason not currently preferred:

FastAPI intentionally provides a smaller core. FashionERP would need separate decisions for ORM, migrations, background jobs, administration patterns and several platform services. It remains appropriate for future specialized services if a real need appears, but not as the proposed ERP core framework.

## Consequences if accepted

- Phase 1 server implementation may begin on Laravel 13.x;
- PHP runtime policy must be finalized before CI/runtime images are considered stable;
- issue #30 must choose the OpenAPI generation/validation strategy;
- module boundaries must be documented before business code expands;
- PostgreSQL remains authoritative and no framework-specific database feature may compromise portability without another ADR;
- CI remains test-only and does not gain deployment automation from this decision.

## Decision required

This ADR remains `proposed` until the project owner explicitly accepts or rejects Laravel 13.x as the FashionERP server framework.
