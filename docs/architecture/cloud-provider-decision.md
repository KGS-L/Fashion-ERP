# Managed cloud provider and cost strategy

Status: `open` — Phase 0 decision required.

The FashionERP specification explicitly requires the cloud provider and cost strategy to be confirmed before development.

This decision must not change the validated deployment model: managed cloud, customizable cloud, on-premise and private server remain supported product directions.

The provider decision should evaluate at minimum:

- PostgreSQL hosting options;
- S3-compatible object storage;
- backup and restore capabilities;
- regional availability and latency for initial customers;
- predictable costs for one private ERP environment/database per customer organization;
- staging and production environment costs where required;
- monitoring and operational overhead;
- export and migration options to avoid unnecessary provider lock-in;
- ability to support encrypted backups and customer data isolation.

No provider is selected by this document yet.
