# Scoped authorization

Ivadoo Data Plane authorization uses project-owned RBAC with explicit resource scopes.

## Model

`Permission -> Role -> AccessGrant -> User or AccessGroup`

An AccessGrant applies at exactly one level:

- Organization: all companies and establishments in the private ERP database;
- Company: one company and its establishments;
- Establishment: one establishment only.

Authentication does not imply business authorization. Missing permission/grant means denial.

## Foundation permission catalog

- `foundation.organization.view`
- `foundation.company.view`
- `foundation.company.manage`
- `foundation.establishment.view`
- `foundation.establishment.manage`
- `foundation.access.manage`

Future modules own their additional stable `module.action` capability codes.

## Administration API

Access administration is available under `/api/v1/access/` and itself requires Organization-scope `foundation.access.manage`.

It supports:

- internal user creation/update;
- permission catalog reads;
- role creation/update;
- group creation/update and membership;
- scoped role grants;
- explicit grant revocation.

Deactivating an internal user revokes their active API sessions.

System/full-access roles cannot be created or modified through the API. The protected Organization administrator role is created by Data Plane bootstrap.

Persistent immutable audit records for these sensitive changes are added by Phase 1 issue #14.
