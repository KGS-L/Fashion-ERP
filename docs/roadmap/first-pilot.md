# First pilot baseline

Status: `accepted` for Phase 0 framing.

This document turns the first-pilot acceptance criteria from the FashionERP specification into a reference validation scenario. It does not identify a real pilot company yet.

## Target pilot profile

The first pilot targets a medium-sized fashion or garment business, consistent with the specification's recommendation to validate adoption with a medium enterprise.

Reference configuration:

- 1 customer organization;
- 1 legal company for the first pilot scenario;
- exactly 2 establishments/sites;
- 8 internal test users with distinct roles/scopes;
- a workshop-oriented operational flow covering customer, made-to-measure order, materials, production, quality and delivery.

The number of 8 users is a reference validation dataset, not a commercial edition limit.

## Reference user scopes

The reference dataset should cover at least:

1. client administrator;
2. sales/customer user;
3. stock/material user;
4. production manager;
5. workshop/mobile operator;
6. quality user;
7. delivery user;
8. management/reporting user.

Roles may be combined in a real pilot when necessary, but the acceptance dataset keeps them distinct so authorization boundaries can be tested.

## Mandatory pilot capabilities

The pilot must demonstrate the capabilities explicitly required by the specification:

- organization and establishment structure;
- users, roles and scoped permissions;
- customer and measurements;
- model/design with variants and materials;
- order creation;
- material reservation;
- simple production launch;
- workshop/mobile task assignment;
- quality control and alteration/rework recording;
- delivery;
- simple reporting;
- access isolation;
- complete backup restoration.

The minimal supporting business domains are therefore customers/CRM, measurements, products/materials, basic design/model management, sales/orders, inventory, simple manufacturing, quality, minimal employee/task assignment, delivery and simple reporting.

## Acceptance scenario

The reference scenario is successful only when all of the following pass:

1. Create one organization with two establishments.
2. Create users whose permissions and scopes differ by role/site.
3. Create a customer, record measurements and create an order.
4. Create a model/design with variants and materials.
5. Reserve required material and start a production order.
6. Assign a workshop task to an authorized mobile user.
7. Perform quality control and record an alteration/rework when required.
8. Complete delivery and produce a simple report.
9. Demonstrate that an unauthorized user cannot access data outside the permitted organization/company/establishment scope.
10. Restore a complete PostgreSQL + file/object-storage backup and verify that the pilot data is usable after restoration.

## Measurable success conditions

- all ten specification scenarios pass end-to-end;
- zero known cross-organization or unauthorized cross-scope data leaks;
- authorization is enforced by the API, not only by the UI;
- the backup restoration reproduces the required pilot records and files;
- blocking defects in the reference workflow are resolved before pilot acceptance;
- the repository CI checks and the relevant automated tests are green before a pilot release candidate is accepted.

## Out of scope for the first pilot

Unless needed by the chosen real pilot company, the following are not required to prove the first reference scenario:

- full statutory accounting;
- consolidation;
- advanced PLM;
- advanced BI;
- SSO;
- advanced public API keys/webhooks;
- multi-country operation;
- advanced subcontracting;
- broad offline coverage outside the field operations allowed by the specification.

## Real pilot company

The named pilot company remains a commercial/field-selection decision. Choosing a company does not change the technical acceptance scenario above unless an approved change is documented.
