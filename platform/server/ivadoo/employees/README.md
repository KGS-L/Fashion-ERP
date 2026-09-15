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
- reproducible productivity snapshots;
- configurable management commission rules and immutable calculations;
- scoped RBAC and append-only audit integration.

## Workshop representation

The current Foundation models workshops through `Establishment.site_type = workshop` (or `mixed`). Employee assignments, schedules, attendance, tasks, time entries, productivity snapshots and commission rules therefore reference an `Establishment` constrained to those site types. This keeps Phase 4 compatible with the Foundation scope model instead of introducing a second incompatible workshop identity.

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

Productivity uses:

- `enterprise.employee.performance.view`;
- `enterprise.employee.performance.manage`.

Commission data is more sensitive and uses its own permissions:

- `enterprise.employee.commission.view`;
- `enterprise.employee.commission.manage`.

Employee serializers do not embed contract or commission data. Actual binary contract documents will use the Phase 4 object-storage/document layer (#93); this domain stores references only until that layer is available.

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

## Productivity formula — v1

A `ProductivitySnapshot` is immutable and stores both the calculated metrics and a fingerprint/summary of the source rows used. Repeating a generation request against exactly the same source state is idempotent; when source tasks/time/operations change, a new historical snapshot can be created.

The reporting period is interpreted in the selected workshop/establishment timezone. Without a site, UTC is used.

For an employee and scope:

- **assigned tasks** = non-cancelled tasks whose `planned_start` is in the period; if no `planned_start` exists, `created_at` is used;
- **completed tasks** = assigned tasks in `done` state with `completed_at` inside the period;
- **task completion rate** = `completed_tasks / assigned_tasks × 100`, or `0` when there are no assigned tasks;
- **tracked minutes** = overlap of closed time entries with the reporting period; open timers are not counted;
- **quantity completion rate** = mean of `processed_quantity / planned_quantity × 100` for distinct manufacturing operations linked to assigned tasks with a positive planned quantity.

The quantity metric is a normalized completion percentage; raw quantities from unrelated products are never summed into a fake universal production quantity.

## Commission formula — v1

Commission rules are management rules, not payroll rules. They support two explicit bases in Phase 4:

1. `completed_task`: number of tasks completed during the period;
2. `tracked_hour`: closed tracked minutes overlapping the period divided by 60.

Formula:

```text
basis_quantity × rule.rate = commission amount
```

The result is rounded with `ROUND_HALF_UP` to the configured currency decimal precision.

Each `CommissionCalculation` is immutable and stores:

- the exact rate and currency used;
- a snapshot of the rule;
- source row identifiers/timestamps;
- a source fingerprint;
- formula version;
- generator and generation time.

This makes calculations explainable and reproducible without converting commissions into salaries, payroll slips, journal entries or statutory accounting. Payment/payroll/accounting treatment remains outside this Phase 4 domain.

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
- time entries;
- productivity snapshots and generation action;
- commission rules;
- immutable commission calculations and calculation action.

All mutations are scoped server-side and audited.
