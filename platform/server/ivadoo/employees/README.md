# Employees

Phase 4 Business domain for employee master data, skills/specialties, contract references and scoped assignments.

## Scope

- employee profiles with optional link to an Ivadoo user account;
- skill catalogue and employee proficiency/specialty links;
- contracts without payroll or statutory accounting fields;
- company, establishment, workshop and role assignments with history;
- scoped RBAC and append-only audit integration.

## Workshop representation

The current Foundation models workshops through `Establishment.site_type = workshop` (or `mixed`). `EmployeeAssignment.workshop` therefore references an `Establishment` constrained to those site types. This keeps Phase 4 assignments compatible with the existing Foundation scope model. Any future hierarchy refinement belongs to the multi-site work rather than creating a second incompatible workshop identity here.

## Security boundary

Employee profile/skill/assignment access uses `enterprise.employee.view` and `enterprise.employee.manage`.

Contract metadata, including `document_reference`, is deliberately exposed through separate endpoints and permissions:

- `enterprise.employee.contract.view`;
- `enterprise.employee.contract.manage`.

Employee serializers do not embed contract data. Actual binary contract documents will use the Phase 4 object-storage/document layer (#93); this domain stores references only until that layer is available.

Employee assignments record an authorization `Role` as organizational metadata but **do not create or mutate `AccessGrant` records automatically**. RBAC grants remain an explicit Foundation access-management operation.

## API

All routes are under `/api/v1/employees/`:

- employee profiles;
- skills catalogue;
- employee-skill links;
- contracts;
- assignments.

All mutations are scoped server-side and audited.
