# Platform

Platform-level components of Ivadoo.

The architecture separates two major concerns:

- **Control Plane**: organizations, licenses, subscriptions, modules, installations, versions and support.
- **Data Plane**: operational business data such as customers, measurements, orders, inventory, production, employees, finance and documents.

The `core/` directory contains the shared ERP foundation defined by the platform core specification: organizations, companies and establishments, users and access control, audit, internationalization, documents and notifications. It is a foundation of the ERP architecture, not a third deployment plane.

Business data must remain isolated according to the deployment and organization boundaries defined in the project specifications.

## Server runtime

The `server/` directory contains the validated Django runtime and cross-cutting REST/OpenAPI infrastructure. It is an application runtime boundary, not an additional deployment plane: Control Plane and customer Data Plane separation remains authoritative.
