# Platform

Platform-level components of FashionERP.

The architecture separates two major concerns:

- **Control Plane**: organizations, licenses, subscriptions, modules, installations, versions and support.
- **Data Plane**: operational business data such as customers, measurements, orders, inventory, production, employees, finance and documents.

Business data must remain isolated according to the deployment and organization boundaries defined in the project specifications.
