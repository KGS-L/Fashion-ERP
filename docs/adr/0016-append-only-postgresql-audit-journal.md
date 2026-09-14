# ADR 0016 — Append-only PostgreSQL audit journal

Status: `accepted`

Decision owner: Phase 1 / issue #14.

## Context

The FashionERP specification requires:

- an audit journal containing user, date, object, old value and new value;
- an immutable audit journal for sensitive operations;
- organization, company and establishment scope where relevant;
- history/events for sensitive objects;
- authorization and leakage tests;
- configurable journal retention.

Phase 1 already has PostgreSQL-backed authentication, private Organization databases, Company/Establishment hierarchy and scoped RBAC.

The specification does not require a SIEM, event broker, external audit product or event-sourcing architecture.

## Decision

FashionERP stores Foundation audit events in a dedicated Django `audit` app in the customer's private Data Plane PostgreSQL database.

### AuditEvent

Each event records:

- immutable UUID;
- occurrence timestamp;
- Organization;
- Company UUID and Establishment UUID when relevant;
- actor UUID and actor login snapshot when known;
- action code;
- object type, object UUID/string identifier and label;
- result (`success`, `failure`, `denied`);
- `before` JSON snapshot;
- `after` JSON snapshot;
- request id, IP address and user-agent when available;
- non-secret metadata.

Actor/company/establishment identifiers are snapshots rather than cascading foreign keys so later lifecycle changes cannot rewrite historical audit rows. Organization remains a protected foreign key because one Data Plane database belongs to one Organization.

### Immutability

Audit events are append-only.

There is no REST create/update/delete endpoint for audit events.

The Django model rejects updates and deletes, and PostgreSQL additionally installs a `BEFORE UPDATE OR DELETE` trigger that raises an exception. This prevents QuerySet/direct ORM mutation from bypassing model methods.

The application database owner could technically alter database schema/triggers; protection against a fully privileged database administrator is an infrastructure/governance concern outside the Phase 1 application boundary.

### Transactional recording

Sensitive state changes and their audit append are executed in the same database transaction where the current endpoint permits it. A successful sensitive mutation must not silently commit without its corresponding audit event.

### Sensitive values

Passwords, bearer tokens, token digests and equivalent secrets are never copied into audit snapshots or metadata.

Snapshots contain only allow-listed business/security fields.

### Foundation events

Phase 1 records at minimum:

- successful login;
- logout and explicit session revocation;
- internal user creation/update/deactivation;
- role creation/update;
- access group creation/update;
- access grant creation/revocation;
- Company creation/update;
- Establishment creation/update.

Future modules add their own action codes for their sensitive operations.

### Read access

Audit events are exposed read-only under `/api/v1/audit/events/`.

Reading requires `foundation.audit.view` at Organization scope. The endpoint supports allow-listed filters and ordering. No write route exists.

### Retention

The schema stores durable events and does not expose deletion.

The specification requires configurable retention, but it does not yet define retention periods, legal holds or privileged purge mechanics. Those rules must be specified before implementing a retention purge that could conflict with immutability.

## Consequences

- Foundation sensitive changes are reconstructable with actor/date/object/before/after;
- application users cannot edit or erase audit history;
- the journal stays inside the physically isolated customer Data Plane;
- audit writes remain simple PostgreSQL transactions without introducing unrequested infrastructure;
- future retention work needs an explicit controlled mechanism rather than generic DELETE access.

## Validation

Validated by the FashionERP project owner through the delegated Phase 1 implementation direction on 2026-09-14, with the requirement that implementation remain coherent with the FashionERP specification and technically sound for a real ERP.
