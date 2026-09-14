# Organizations

This Django application owns the local customer Organization root inside one FashionERP ERP Data Plane database.

Architecture invariants:

- one ERP Data Plane database belongs to one customer organization;
- a database may contain only one local Organization record;
- the local Organization is the parent boundary for Company, Establishment and later scoped Foundation data;
- the Control Plane organization registry remains a separate platform concern;
- Data Plane API clients cannot select another customer database through request headers or parameters.

Provisioning is performed out of band through the bootstrap command rather than an unrestricted API create endpoint.
