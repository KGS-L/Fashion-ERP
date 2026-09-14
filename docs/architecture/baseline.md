# Architecture and deployment baseline

Status: `partially accepted` during Phase 0.

This document records the architecture and deployment decisions already defined by the FashionERP functional and technical specification. It does not introduce an application framework or infrastructure technology that is not explicitly validated.

## Platform separation

Accepted:

- FashionERP is split between a **Control Plane** and customer ERP **Data Plane** environments.
- The Control Plane manages platform concerns such as organizations, licenses, subscriptions, modules, installations, versions and support.
- Customer business data belongs to the Data Plane.
- The Control Plane must not copy sensitive customer business data by default.

## Customer data isolation

Accepted:

- each customer organization has its own ERP environment and private database boundary;
- one customer organization may contain several legal companies and establishments;
- company and establishment scopes remain explicit throughout business operations and access control;
- strict inter-organization isolation is a security requirement.

## Data and files

Accepted:

- PostgreSQL is the relational database baseline for ERP data and file metadata;
- business files use S3/MinIO-compatible object storage;
- backups must cover PostgreSQL and the file/object store;
- sensitive backups and files must be encrypted according to the security requirements.

## API

Accepted:

- the application interface is REST-based;
- API versioning starts with `/api/v1`;
- lists support pagination, filters, sorting and search where applicable;
- permissions are enforced by the API;
- the API is documented with OpenAPI;
- Enterprise Plus may expose advanced API capabilities such as API keys and webhooks.

## Desktop application

Accepted:

- the installable PC application uses **Tauri + Owl/TypeScript**;
- the desktop application connects to the FashionERP API;
- it must support cloud, local and private-server usage modes as defined by the specification.

No alternative desktop framework is part of the current baseline.

## Deployment modes

Accepted:

### Managed cloud

- private customer ERP database hosted by FashionERP;
- FashionERP is responsible for infrastructure, backups and updates.

### Customizable cloud

- development/test or test/staging/production-style environments may be provided according to the customer setup;
- responsibility is shared between FashionERP and the customer for extensions.

### On-premise

- the ERP database is hosted by the customer;
- mobile access may use a local API or controlled tunnel;
- the customer is responsible for its server while FashionERP retains responsibility for licensing/support within the agreed contract.

### Private server

- database and files remain on customer-controlled infrastructure;
- controlled services may communicate through a secured gateway where required;
- the customer retains custody of its business data.

## Environments and operations

Accepted:

- development, test, staging and production environments are part of the operational model;
- database migrations are versioned;
- a backup is required before migrations;
- rollback or restore procedures must exist;
- Docker is the supported direction identified by the specification for handling on-premise deployment complexity;
- CI remains limited to validation and automated tests at the current stage and does not deploy environments.

## Decisions still open

### Minimum desktop operating systems

The specification explicitly requires the minimum supported Windows, macOS and Linux versions to be confirmed before development.

Status: `open`.

### Managed cloud provider and cost strategy

The specification explicitly leaves the cloud provider and cost strategy to be confirmed before development.

Status: tracked separately during Phase 0 so that provider choice is not confused with the architecture baseline.

## Not decided by this baseline

The following are intentionally not selected here unless separately accepted:

- server-side application framework;
- mobile application framework;
- cloud provider;
- managed database vendor;
- queue or realtime implementation;
- reverse proxy;
- final observability stack among the tools listed as possible in the specification.

These choices require explicit decisions when they become necessary.
