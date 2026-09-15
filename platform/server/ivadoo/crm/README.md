# CRM

Phase 4 Business CRM domain for prospect capture, commercial opportunities, configurable sources/pipeline stages and controlled conversion to the canonical `customers.Customer` master data.

## Scope

This first CRM slice implements issue #76:

- lead/prospect records scoped to organization, company and optional establishment;
- opportunity records with commercial owner, source, pipeline stage, expected revenue and probability;
- configurable lead sources per company;
- configurable pipeline stages per company;
- conversion of a lead or opportunity to an existing or newly-created Customer;
- immutable conversion history;
- scoped RBAC, audit events and REST/OpenAPI endpoints.

Relances, segmentation and broader commercial activity history belong to #77 and are intentionally not duplicated here.

## Permissions

The CRM uses three Business permissions:

- `enterprise.crm.view` — read CRM records in an authorized scope;
- `enterprise.crm.manage` — create/update sources, stages, leads and opportunities;
- `enterprise.crm.convert` — perform prospect/opportunity conversion to Customer.

Organization, company and establishment grants are evaluated server-side through the shared Foundation authorization layer. A user never selects an arbitrary tenant or company merely through request payload data.

## Customer conversion policy

`customers.Customer` remains the canonical customer master record. CRM does not introduce a second customer identity.

Conversion is transactional and follows these rules:

1. an explicitly selected Customer is reused only when it belongs to the same organization/company;
2. without an explicit Customer, the service looks for active/non-archived company Customers with the same email or phone;
3. exactly one match is reused automatically;
4. multiple matches are rejected and the caller must select the intended Customer explicitly;
5. when no match exists, a new Customer may be created, but a unique company-level `customer_code` is required;
6. repeated conversion of the same lead/opportunity is idempotent and returns its existing conversion event instead of creating another Customer.

For an opportunity linked to a lead, both records converge on the same Customer. Conversion events retain a source snapshot so later edits do not erase what was converted.

## Pipeline semantics

Pipeline stages are company-owned and ordered by `position`. Their `stage_type` is one of:

- `open`;
- `won`;
- `lost`.

`probability` is constrained to 0–100. Opportunity probability defaults from the selected stage on creation but remains an explicit opportunity value afterwards.

## API

All routes live under `/api/v1/crm/`:

- `sources/`;
- `stages/`;
- `leads/`;
- `leads/{id}/actions/convert/`;
- `opportunities/`;
- `opportunities/{id}/actions/convert/`;
- `conversions/` (read-only history).

Mutations are audited and conversion history itself is immutable.
