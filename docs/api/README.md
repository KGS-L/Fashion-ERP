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

The immutable Foundation audit journal is read-only under `/api/v1/audit/events/` and requires Organization-scope `foundation.audit.view`. Sensitive mutations record actor/date/object/result and allow-listed before/after snapshots. Audit writes are server-side only.

Tests must include negative cases proving that unauthorized data is not returned through list, retrieve, update, delete or action endpoints.

## OpenAPI contract

drf-spectacular generates the schema from implemented Django routes, serializers and annotations.

The CI contract check must generate and validate the schema without deploying anything:

```bash
python manage.py spectacular --file /tmp/fashionerp-openapi.yaml --validate --fail-on-warn
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


## Foundation internationalization

Internationalization resources live under `/api/v1/i18n/`.

The Foundation exposes:

- supported languages (`fr`, `en`, `es`, `pt`, `ar`);
- stable-key translation catalogs with plural forms and RTL/LTR direction;
- locale format metadata;
- effective user/company/establishment internationalization context;
- configurable currencies;
- Organization-scoped dated exchange rates;
- Organization-scoped units of measure.

Catalog/context reads are available to authenticated users. Reference-data reads/writes are protected by `foundation.i18n.view` and `foundation.i18n.manage`.

Company carries its language default and optional functional currency. Establishment carries a validated IANA timezone. User carries its interface language preference.

No country fiscal/accounting rule is exposed by the common i18n API.


## Two-factor authentication and session security

Interactive authentication remains under `/api/v1/auth/`.

The Foundation security surface includes:

- active own-session/device listing;
- individual own-session revocation;
- revoke-all-other-own-sessions action;
- TOTP setup and confirmation;
- 2FA status;
- personal 2FA disable with security reauthentication;
- recovery-code regeneration with password + TOTP.

When confirmed 2FA exists, login requires a valid TOTP or unused recovery code. Error codes include `two_factor_required` and `invalid_two_factor`.

TOTP setup secrets are encrypted at rest. Recovery codes are returned only at generation time and only digests are stored.

Enabling 2FA revokes other pre-2FA sessions. Disabling 2FA also revokes other sessions. Session representations include source IP and whether a second factor was verified.

Organization access administrators may reset another user's 2FA under `/api/v1/access/users/{user_id}/2fa/reset/`. The administrator must reauthenticate; the target user's sessions are revoked and the action is auditable. This route cannot be used by an administrator to bypass their own personal 2FA controls.


## Phase 1 Foundation route inventory

Issue #19 applies the REST/OpenAPI conventions from ADR 0011 to the Foundation resources that are actually implemented.

The routed Foundation namespaces are:

| Namespace | Foundation responsibility |
| --- | --- |
| `/api/v1/auth/` | login/logout, current user, sessions/devices, TOTP 2FA and recovery |
| `/api/v1/organizations/` | local Organization read boundary |
| `/api/v1/companies/` | Company resources |
| `/api/v1/establishments/` | Establishment resources |
| `/api/v1/access/` | users, permissions, roles, groups and scoped grants |
| `/api/v1/audit/` | immutable audit-event reads |
| `/api/v1/i18n/` | languages, catalogs, context, currencies, rates and units |

The Organization collection is an explicitly bounded exception to default pagination: ADR 0014 allows exactly one local Organization per private Data Plane database.

All other unbounded Foundation collections use the standard page-number pagination contract unless their endpoint is explicitly bounded.

### Phase 1 contract guard

Automated API contract tests verify that:

- implemented Foundation paths are present in generated OpenAPI;
- the opaque `bearerAuth` security scheme is present;
- company and establishment list parameters expose the declared pagination/filter/search/ordering contract;
- the stable JSON error envelope propagates `X-Request-ID`;
- no Phase 2 business namespace is exposed early;
- no API-key or webhook endpoint is exposed as a Foundation capability.

The following specification namespaces remain intentionally absent until their business phases: `customers`, `products`, `measurements`, `orders`, `inventory`, `purchases`, `manufacturing`, `deliveries` and `reports`.

Webhooks and API keys remain Enterprise Plus capabilities and are not part of the internal Foundation API.
