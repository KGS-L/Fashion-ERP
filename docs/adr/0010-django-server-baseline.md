# ADR 0010 — Django server baseline

Status: `accepted`

Decision owner: Phase 1 / issue #25.

## Context

The FashionERP specification defines the architectural constraints for the server side: PostgreSQL, a REST API versioned under `/api/v1`, OpenAPI, Control Plane / Data Plane separation, S3/MinIO-compatible object storage, strict tenant isolation, versioned migrations, audit, 2FA, RBAC and multiple deployment modes.

The current FashionERP v1.0 specification does not explicitly name the server framework. The project owner has now explicitly confirmed **Django** as the FashionERP backend framework. This is therefore a validated project decision, not a claim attributed to the PDF.

## Decision

FashionERP uses **Django** as its primary backend/server framework.

The following remain unchanged and authoritative from the specification:

- PostgreSQL as relational database;
- REST API under `/api/v1`;
- OpenAPI documentation;
- Control Plane and customer Data Plane separation;
- private ERP database boundary per customer organization;
- S3/MinIO-compatible object storage;
- RBAC and scoped access by organization/company/establishment/warehouse where applicable;
- sessions, revocation and 2FA;
- immutable audit requirements for sensitive operations;
- Docker-supported on-premise direction;
- development, test, staging and production environments.

## Not decided by this ADR

This ADR intentionally does not infer implementation details that have not yet been validated, including:

- Django version;
- Python runtime version;
- Django REST Framework or another REST layer;
- OpenAPI generation/validation package;
- authentication/session package choices;
- background-job/queue technology;
- realtime technology;
- reverse proxy;
- final observability stack.

These choices must follow the project source-first rule and be validated only when required.

## Consequences

- Phase 1 server-side implementation must be Django-based.
- API implementation must conform to the FashionERP REST/OpenAPI contract rather than redefine it.
- PostgreSQL remains authoritative; framework convenience must not compromise portability or tenant isolation.
- Authorization must be enforced server-side and covered by negative isolation tests.
- No PHP/Laravel runtime or dependency is part of the FashionERP backend baseline.

## Source-first rule

Before introducing or changing a foundational technology, consult the FashionERP specification and relevant project sources first. A technology used in another project, profile or previous conversation must not be imported into FashionERP unless explicitly part of this project or validated by the project owner.
