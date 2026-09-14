# ADR 0011 — Django REST Framework and drf-spectacular

Status: `accepted`

Decision owner: Phase 1 / issue #30.

## Context

FashionERP already requires a versioned REST API under `/api/v1`, OpenAPI documentation, pagination, filtering, sorting, search, server-side permissions and explicit business actions. Django is the accepted backend framework from ADR 0010.

The REST/OpenAPI layer must support the Foundation scope first and remain suitable for later ERP modules without allowing the generated contract to drift away from implemented routes.

## Decision

FashionERP uses:

- **Django REST Framework (DRF)** as the primary REST API layer;
- **drf-spectacular** as the OpenAPI 3 schema generator and documentation integration;
- **django-filter** for explicit field-level filtering where a resource requires it.

The business API remains versioned under `/api/v1/`.

## API conventions

### Resource URLs

Collections and resource endpoints use plural nouns and UUID identifiers.

Examples:

- `GET /api/v1/organizations/`
- `GET /api/v1/organizations/{uuid}/`
- `GET /api/v1/companies/`
- `GET /api/v1/establishments/`

No new Phase 2 business resource is introduced by this ADR.

### Business actions

State-changing business transitions that carry domain meaning use explicit `POST` action endpoints rather than a generic status mutation.

Examples for later modules include `/{uuid}/confirm/`, `/{uuid}/approve/`, `/{uuid}/assign/`, `/{uuid}/start/` and `/{uuid}/deliver/`.

Actions must enforce authorization and audit requirements exactly like resource endpoints.

### Successful responses

Single-resource endpoints return the serialized resource directly.

List endpoints use the project pagination contract:

```json
{
  "count": 120,
  "next": "https://example.test/api/v1/resource/?page=2",
  "previous": null,
  "results": []
}
```

### Errors

API errors use a stable application JSON structure:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request is invalid.",
    "details": {},
    "request_id": null
  }
}
```

The exact user-facing message may be localized later, but clients must rely on the stable machine-readable `code`, not message text.

### Pagination

Pagination is mandatory for collection endpoints unless a specific endpoint is explicitly documented as bounded.

Baseline:

- query parameter: `page`;
- optional `page_size`;
- default page size: 50;
- maximum page size: 100.

### Filtering, search and ordering

- exact/range/domain filters use `django-filter` and must be explicitly declared per resource;
- free-text search uses DRF search fields explicitly declared per endpoint;
- ordering uses an explicit allow-list of fields;
- default ordering must be deterministic;
- client-provided arbitrary ORM field names are not accepted.

### Permissions and scoping

Authorization is enforced at the API boundary.

Querysets and object access must be constrained to the current organization/company/establishment/warehouse scope where the domain requires it. Hiding data only in serializers or clients is insufficient.

Negative authorization and isolation tests are mandatory.

## OpenAPI

Schema generation is performed by drf-spectacular from implemented routes and serializers.

Reserved endpoints:

- `GET /api/schema/` — OpenAPI schema;
- `GET /api/docs/` — interactive Swagger UI documentation.

The generated schema is an implementation artifact; hand-maintained duplicate endpoint definitions must not become a second source of truth.

## Reproducible schema and CI

Once the Django server scaffold exists, CI must run a schema generation/validation command equivalent to:

```bash
python manage.py spectacular --file /tmp/fashionerp-openapi.yaml --validate
```

The command must fail CI on invalid schema generation. A committed snapshot may later be compared in CI when the first Foundation routes exist, but deployment or publication is outside this issue.

## Consequences

- serializers, ViewSets/APIViews, permissions, routers and pagination follow DRF conventions;
- OpenAPI remains generated from implementation through drf-spectacular;
- filtering behavior is explicit and reviewable;
- state transitions are represented as domain actions instead of arbitrary status patches;
- API tests must cover permissions and scope leakage;
- GitHub Actions remains test/validation-only.

## Alternatives considered

### Django Ninja

Django Ninja provides strong typing and automatic OpenAPI generation, but the FashionERP core is expected to be heavily resource-, permission- and CRUD-oriented. DRF offers the more mature baseline for serializers, ViewSets, permission classes, pagination and filtering in that context.

### DRF without drf-spectacular

Rejected because the project requires a dependable OpenAPI contract and validation workflow beyond DRF's basic schema facilities.

## Deferred decisions

This ADR does not select:

- authentication/session implementation packages;
- 2FA package;
- API-key/webhook implementation for Enterprise Plus;
- queue/background-job stack;
- realtime transport;
- reverse proxy.
