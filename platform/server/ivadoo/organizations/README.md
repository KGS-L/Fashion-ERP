# Organizations, companies and establishments

This Django application owns the local customer hierarchy inside one Ivadoo ERP Data Plane database.

Architecture invariants:

- one ERP Data Plane database belongs to one customer organization;
- a database may contain only one local Organization record;
- one Organization may contain multiple legal Companies;
- one Company may contain multiple Establishments/sites;
- an Establishment belongs to exactly one Company and derives its organization from that Company;
- the Control Plane organization registry remains a separate platform concern;
- Data Plane API clients cannot select another customer database through request headers or parameters.

Establishment `site_type` prepares the structural scopes explicitly mentioned by the Ivadoo specification: workshop, store and warehouse, while allowing office/mixed/other sites without implementing their business modules prematurely.

At the current Phase 1 point, organization/company/establishment endpoints are read-only for authenticated users. Write permissions are intentionally deferred until #13 defines the RBAC policy instead of exposing unrestricted hierarchy mutation.

Provisioning of the local Organization is performed out of band through the bootstrap command rather than an unrestricted API create endpoint.
