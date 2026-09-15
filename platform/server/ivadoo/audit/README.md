# Foundation audit journal

Ivadoo records sensitive Foundation operations in an append-only PostgreSQL audit journal.

## Required information

Each `AuditEvent` can contain:

- actor UUID and login snapshot;
- occurrence date/time;
- Organization;
- Company and Establishment UUID scopes when relevant;
- stable action code;
- object type, id and label;
- result;
- old value (`before`);
- new value (`after`);
- request id, source IP and user-agent;
- non-secret metadata.

This implements the specification requirement for user/date/object/old/new values and an immutable journal for sensitive operations.

## Immutability

Audit events are created only through the server-side audit service.

There is no REST write endpoint.

Two application layers reject mutation:

1. the Django model rejects `save()` on an existing event and `delete()`;
2. PostgreSQL rejects `UPDATE` and `DELETE` through the `ivadoo_audit_event_immutable` trigger.

The REST surface is read-only:

`GET /api/v1/audit/events/`

and requires Organization-scope `foundation.audit.view`.

## Foundation actions

Current action codes include:

- `auth.login` (success and invalid-credential failure);
- `auth.logout`;
- `auth.session.revoke`;
- `access.bootstrap.organization_admin`;
- `access.user.create`;
- `access.user.update`;
- `access.role.create`;
- `access.role.update`;
- `access.group.create`;
- `access.group.update`;
- `access.grant.create`;
- `access.grant.revoke`;
- `foundation.company.create`;
- `foundation.company.update`;
- `foundation.establishment.create`;
- `foundation.establishment.update`.

Future modules must add audit events for their own sensitive operations.

## Secret handling

Snapshots are allow-listed.

Passwords, raw bearer tokens and token digests are not stored in the audit journal. A password update is represented only by non-secret metadata indicating that a password changed.

## Retention

The Ivadoo specification requires configurable retention for journals, but does not yet define retention periods, legal holds or privileged purge rules.

Phase 1 therefore does not invent a generic deletion endpoint. Retention must be specified before a controlled purge mechanism is implemented.
