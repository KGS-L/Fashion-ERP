# ADR 0022 — Customization security boundary and protected invariants

Status: `accepted`

Decision owner: platform extensibility / issue #150.

## Context

Custom fields, Studio and imports increase flexibility but must never become an alternate path around Ivadoo's typed domain rules, private-database boundary, scoped RBAC or audit journal. A configurable ERP needs a strict line between presentation customization and protected system invariants.

## Decision

Ivadoo applies customization deny-by-default.

### Registered models only

Only `ModelManifest` entries are extensible. Security/session/audit/license models are unavailable to custom fields unless a future decision explicitly registers them.

### Protected native fields

Each model manifest carries protected native field names. Organization/company/establishment scope, identity, timestamps, workflow status/number/version and future stock/accounting integrity fields are system-owned. Studio/import metadata can describe them but cannot redefine or delete them.

### Custom namespace

Customer-defined fields live in the reserved `x_...` namespace. Keys cannot collide with native or protected fields. Field model/key identity becomes stable after publication.

### Layered permissions

Custom field visibility/editability can optionally add field-level permission codes. A field-level permission can only further restrict access: the user must still hold the model's view/manage permission in the target object's company/establishment scope. Sensitive fields require explicit view and edit permission codes.

### Reference safety

Custom references target only explicitly registered models and UUIDs resolvable in the local organization database. Cross-organization references are rejected. Physical database isolation remains the primary tenant boundary.

### Custom data API

Generic custom values are exposed through a platform endpoint so clients can use metadata-defined fields without requiring a schema migration in every business module. Read/write operations resolve the target object first, then apply model scope plus field permission checks. The server remains authoritative.

### Evolution safety

Deactivating a definition preserves stored values. A field type cannot be changed after values are in use. Destructive schema operations are not available to tenant customizers.

## Consequences

- Studio cannot weaken RBAC, tenant scope, stock/accounting rules or immutable audit;
- a client may hide or relabel compatible presentation fields later without deleting core columns;
- sensitive custom data has explicit permission boundaries;
- generic clients can safely discover/use custom fields;
- imports must call the same domain/custom-field services instead of direct SQL/ORM bulk writes.

## Deferred

Layout-level Studio permissions, workflow customization and formula sandboxing are handled by #142, #146 and #147. More granular field encryption can be introduced when a concrete data classification requires it.
