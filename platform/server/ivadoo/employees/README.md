# Employees

Phase 4 Business domain for employee master data, skills/specialties, contract references, scoped assignments and daily team operations.

## Scope

- employee profiles with optional link to an Ivadoo user account;
- skill catalogue and employee proficiency/specialty links;
- contracts without payroll or statutory accounting fields;
- company, establishment, workshop and role assignments with history;
- employee schedules;
- attendance records;
- operational tasks linked to customer orders and manufacturing operations when relevant;
- time entries with server-computed duration;
- immutable task transition history;
- scoped RBAC and append-only audit integration.

## Workshop representation

The current Foundation models workshops through `Establishment.site_type = workshop` (or `mixed`). Employee assignments, schedules, attendance, tasks and time entries therefore reference an `Establishment` constrained to those site types. This keeps Phase 4 compatible with the Foundation scope model instead of introducing a second incompatible workshop identity.

## Security boundary

Employee profile/skill/assignment access uses:

- `enterprise.employee.view`;
- `enterprise.employee.manage`.

Contract metadata, including `document_reference`, is deliberately exposed through separate endpoints and permissions:

- `enterprise.employee.contract.view`;
- `enterprise.employee.contract.manage`.

Daily planning, attendance, task and time-tracking records use:

- `enterprise.employee.work.view`;
- `enterprise.employee.work.manage`.

Employee serializers do not embed contract data. Actual binary contract documents will use the Phase 4 object-storage/document layer (#93); this domain stores references only until that layer is available.

Employee assignments record an authorization `Role` as organizational metadata but **do not create or mutate `AccessGrant` records automatically**. RBAC grants remain an explicit Foundation access-management operation.

## Daily work rules

- schedules require an end strictly after the start;
- attendance check-out cannot precede check-in;
- tasks may reference a Sales Order and/or Manufacturing Operation only inside the same organization/company;
- when both an order and a manufacturing operation are supplied, their source order must agree;
- task state changes follow an explicit transition matrix and append an immutable `EmployeeTaskTransition` row;
- time-entry duration is computed server-side from start/end timestamps and is not accepted as client authority;
- no payroll, salary calculation or statutory HR accounting is introduced in this phase.

These task contracts are intentionally suitable for the later workshop mobile application: the mobile client will consume the same server-authoritative task records and actions instead of implementing a separate task model.

## API

All routes are under `/api/v1/employees/`:

- employee profiles;
- skills catalogue;
- employee-skill links;
- contracts;
- assignments;
- schedules;
- attendance;
- tasks;
- time entries.

All mutations are scoped server-side and audited.
