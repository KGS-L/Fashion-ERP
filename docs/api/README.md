# FashionERP REST/OpenAPI conventions

Status: `accepted` for Phase 1 Foundation.

This directory documents the API contract conventions selected in issue #30. The functional requirements remain defined by the FashionERP specification; the implementation decision is recorded in `docs/adr/0011-drf-drf-spectacular.md`.

## Stack

- Django
- Django REST Framework
- drf-spectacular
- django-filter for declared field filters

## Base paths

- Business API: `/api/v1/`
- OpenAPI schema: `/api/schema/`
- Interactive documentation: `/api/docs/`

The Foundation API only exposes Foundation resources. Phase 2 business modules must not be introduced early.

## URL conventions

- plural resource names;
- trailing slash retained consistently;
- UUID resource identifiers;
- nested URLs only when the child resource is truly scoped by the parent; otherwise use filters;
- domain transitions use explicit `POST` action endpoints.

## HTTP semantics

- `GET`: read/list;
- `POST`: create or execute an explicit action;
- `PUT`: full replacement only where intentionally supported;
- `PATCH`: partial editable-field update;
- `DELETE`: delete/archive only where the domain permits it.

Sensitive business state changes must not be implemented as unrestricted generic status edits.

## Collection contract

Collection endpoints are paginated by default:

```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": []
}
```

Baseline pagination uses `page` and optional `page_size`, with 50 items by default and 100 maximum.

Filtering, search and ordering are allow-listed per endpoint.

## Error contract

```json
{
  "error": {
    "code": "permission_denied",
    "message": "You do not have permission to perform this action.",
    "details": {},
    "request_id": null
  }
}
```

Recommended baseline codes include:

- `authentication_required`
- `permission_denied`
- `not_found`
- `validation_error`
- `conflict`
- `rate_limited`
- `server_error`

Field validation information belongs in `details`.

## Security and tenant scope

Every endpoint must enforce server-side permission and data scope. Depending on the resource this may include organization, company, establishment or warehouse scope.

Foundation Data Plane authorization uses scoped RBAC (ADR 0015). Authentication alone never grants Company/Establishment business access. Effective permissions are resolved server-side from direct/group role grants on each request, so revocation is not delayed by bearer-token claims.

Access administration lives under `/api/v1/access/` and requires Organization-scope `foundation.access.manage`.

Tests must include negative cases proving that unauthorized data is not returned through list, retrieve, update, delete or action endpoints.

## OpenAPI contract

drf-spectacular generates the schema from implemented Django routes, serializers and annotations.

The CI contract check must generate and validate the schema without deploying anything:

```bash
python manage.py spectacular --file /tmp/fashionerp-openapi.yaml --validate
```

When the first Foundation endpoints exist, the project may commit a deterministic schema snapshot for review and drift checking.

## Documentation rule

Endpoint descriptions should state:

- purpose;
- required permission/scope;
- request body where applicable;
- successful responses;
- expected error responses;
- filters/search/order parameters for lists;
- action semantics for domain transitions.

The generated OpenAPI description is not a substitute for domain rules in the specification or module documentation.
