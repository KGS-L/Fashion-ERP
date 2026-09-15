# ADR 0021 — Metadata API from the authoritative model registry

Status: `accepted`

Decision owner: platform extensibility / issue #149.

## Context

Ivadoo desktop, future mobile/web clients, Studio and generic import/export must understand which modules, models and fields are available for the authenticated organization. Hard-coding every form separately would make customer-defined fields and modular activation diverge between clients.

Metadata is also security-sensitive: the server must not disclose disabled modules or registered models the current user cannot view.

## Decision

Ivadoo exposes versioned metadata below `/api/v1/platform/metadata/`.

The metadata projection is generated from authoritative sources rather than stored as a second editable schema:

- static `ModuleManifest` and `ModelManifest` declarations describe code capabilities;
- Django model fields describe native relational fields;
- active `CustomFieldDefinition` rows describe organization-local custom fields;
- RBAC and effective module state decide which models are visible.

Native and custom fields are explicitly distinguished. Protected native fields are marked as protected so Studio/import clients know they cannot redefine them, while server authorization remains authoritative regardless of UI behavior.

Model metadata also declares actions and import/export capabilities. These are capability descriptions, not permission grants.

Responses include a private ETag calculated from the effective metadata. Clients may cache metadata and use conditional requests, but must invalidate the cache when the ETag changes.

Unauthorized or disabled model detail requests return `404` to avoid turning the metadata API into a discovery side channel.

## Consequences

- desktop/mobile/web can render compatible dynamic fields without duplicating schema knowledge;
- import/export can use the same field vocabulary as Studio;
- disabled modules disappear from effective metadata;
- OpenAPI remains the contract for HTTP operations while metadata describes runtime organization capabilities;
- the server, not the UI, remains the source of truth for authorization.

## Deferred

View/layout metadata is added with Ivadoo Studio (#142). Configurable workflow transitions and computed fields are added by their dedicated tracker issues.
