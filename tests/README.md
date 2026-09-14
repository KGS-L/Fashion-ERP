# Tests

Automated tests for FashionERP belong here when they are not colocated with a component.

Current test areas:

- `integration/` — cross-component and cross-module integration tests
- `e2e/` — complete user and business workflow validation
- `security/` — authorization, scope and inter-tenant isolation tests
- `performance/` — performance and scalability checks for critical paths

The specification requires particular attention to authorization boundaries, inter-tenant data isolation, business workflow integrity, backup and restore validation, performance of common screens and APIs, and migration/update reliability.

The exact test tooling will be selected together with the implementation technologies.
