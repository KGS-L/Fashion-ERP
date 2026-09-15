# ADR 0020 — Hybrid custom fields with sidecar JSONB storage

Status: `accepted`

Decision owner: platform extensibility / issue #141.

## Context

FashionERP must support customer-defined fields while preserving typed ERP invariants, safe upgrades and a private PostgreSQL database per organization. Creating or dropping physical PostgreSQL columns every time a customer edits a form would couple tenant customization to deployment migrations and make upgrades difficult. Storing the entire ERP record as schemaless JSON would weaken constraints on orders, stock, accounting and security scopes.

## Decision

FashionERP uses a hybrid model.

### Core fields stay relational and typed

Fields that define ERP identity, tenancy, company/site scope, workflow integrity, quantities, accounting or other core rules remain normal Django/PostgreSQL columns and constraints.

### Custom field definitions are metadata

`CustomFieldDefinition` is scoped to the local organization and identifies a registered extensible model. Custom keys use the reserved `x_...` namespace. Definitions carry type, required/default behavior, selection options, declarative validation metadata, search/report flags, active state and a version.

A published definition is not renamed to point at another model/key. It can be logically deactivated; deactivation does not erase historical values.

### Custom values use a sidecar record

`CustomObjectData` stores one JSON object per `(organization, model_key, object_id)`. This avoids a schema migration for each customer field while keeping core business tables strongly typed.

Values are validated server-side against the active definitions before write. Decimal values are stored as strings to avoid binary JSON precision loss. Dates/datetimes use ISO representations. Reference fields require a registered target model and a UUID that resolves inside the local organization.

### Extensible model registry

Only explicitly registered models accept custom fields. This is deny-by-default: a customer cannot attach arbitrary JSON to audit, session, license or other sensitive models unless that model is deliberately exposed later.

## Consequences

- customer fields survive core upgrades without per-field SQL migrations;
- the database remains relational for invariants and transactions;
- custom field reads/writes are centralized and auditable;
- disabling a field preserves old data;
- reporting/search over heavily used custom fields may require explicit indexes or promotion into a native field later;
- a field that becomes universal can be migrated from custom storage into the core model in a controlled release.

## Rejected alternatives

- arbitrary tenant-generated `ALTER TABLE` migrations;
- fully schemaless JSON ERP records;
- unrestricted EAV rows for every core field.

## Deferred

Studio layout editing, configurable workflows, computed formulas and package promotion are separate tracker #139 issues. Advanced indexing of custom values is added only when a concrete query requirement justifies it.
