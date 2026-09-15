# ADR 0015 — Scoped RBAC with role grants

Status: `accepted`

Decision owner: Phase 1 / issue #13.

## Context

The Ivadoo specification requires:

- users, groups, roles and permissions by module/action/company/site;
- security by default, limited by company, establishment and role;
- RBAC with company/establishment/warehouse perimeter;
- server-side API permission checks;
- deny-by-default behavior and authorization/leakage tests.

ADR 0014 already establishes that one ERP Data Plane database belongs to one customer Organization. RBAC therefore scopes access *inside* that private database; it is not the organization isolation mechanism itself.

The specification does not define role inheritance, explicit deny rules or a specific Django authorization package.

## Decision

Ivadoo uses a project-owned scoped RBAC model rather than relying only on Django's global `Group`/`Permission` tables.

### Concepts

- `Permission`: immutable/stable capability code expressed as `module.action`.
- `Role`: named bundle of permissions inside the local Organization.
- `AccessGroup`: optional collection of internal users used to assign the same roles efficiently.
- `AccessGrant`: assigns one Role to exactly one principal (User or AccessGroup) at exactly one scope.

### Scope hierarchy

A grant has one of three scopes:

1. Organization — applies to all companies and establishments in the local Data Plane;
2. Company — applies to that company and its establishments;
3. Establishment — applies only to that establishment.

The Organization is already a physical database boundary. Company and Establishment scopes are evaluated on every API request/query.

An Establishment scope derives its Company and Organization from the establishment relation; the grant does not duplicate those foreign keys as competing sources of truth.

### Permission evaluation

Effective access is the union of:

- direct grants assigned to the user;
- grants assigned to any active AccessGroup containing the user.

A role grants access when:

- it contains the requested Permission; or
- it is the protected full-access Organization administrator role;
- and its AccessGrant covers the requested resource scope.

No permission or matching grant means denial.

Permission removal, role permission removal, group membership removal and grant revocation take effect on the next request because authorization is resolved from PostgreSQL rather than embedded in long-lived bearer-token claims.

### Deny-by-default

There is no implicit authenticated-user access to Company or Establishment data.

Authentication proves identity; RBAC separately grants authorization.

Unknown and out-of-scope object lookups return `404` where appropriate to avoid disclosing resource existence. Forbidden actions on a visible resource return `403`.

### Explicit deny and role inheritance

Phase 1 does not implement explicit deny rules or role inheritance.

This is intentional:

- explicit deny introduces precedence rules that are easy to misconfigure;
- role inheritance introduces graph/cycle complexity;
- neither is required by the Ivadoo specification.

Roles are composable through multiple grants instead.

### Django built-in authorization

Django's authentication primitives remain useful for framework/admin integration, but Ivadoo business API authorization is resolved through the scoped RBAC model.

Django `is_superuser` must not silently bypass Ivadoo Data Plane scope checks.

### Organization administrator

The bootstrap user receives a protected Organization-level full-access role.

This represents the specification's **Administrateur client** profile, whose typical access is the complete customer Organization. It is distinct from **Administrateur plateforme**, which remains Control Plane only.

### API write opening

Company/Establishment write operations may be opened only through scoped RBAC checks.

Foundation permissions include at minimum:

- `foundation.company.view`
- `foundation.company.manage`
- `foundation.establishment.view`
- `foundation.establishment.manage`
- `foundation.access.manage`

Future modules add their own stable permission codes without changing the RBAC schema.

### Audit

#13 owns authorization and immediate revocation semantics. Persistent immutable audit records for access administration are added by #14.

## Consequences

- authorization remains independent from bearer session lifetime;
- one user may have different roles at different companies/sites;
- groups reduce repeated grants without becoming permission containers themselves;
- roles remain understandable and auditable;
- future warehouse-specific objects can extend the same resolver using Establishment/site ancestry or a dedicated warehouse scope when the warehouse model exists;
- API querysets must be filtered by effective scope, not only protected at the UI layer.

## Validation

Validated by the Ivadoo project owner through the delegated Phase 1 implementation direction on 2026-09-14, with the requirement that technical choices remain coherent with the specification and suitable for implementing the ERP correctly.
