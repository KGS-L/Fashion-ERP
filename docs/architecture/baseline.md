# Architecture and deployment baseline

Status: `accepted` during Phase 0.

This document records the architecture and deployment decisions already defined by the project functional and technical specification, together with the minimum desktop operating-system policy accepted during Phase 0. The original specification was written under the legacy working name **Ivadoo**; the accepted product brand is now **Ivadoo**. This document does not introduce an application framework or infrastructure technology that is not explicitly validated.

## Platform separation

Accepted:

- Ivadoo is split between a **Control Plane** and customer ERP **Data Plane** environments.
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
- the desktop application connects to the Ivadoo API;
- it must support cloud, local and private-server usage modes as defined by the specification.

No alternative desktop framework is part of the current baseline.

### Minimum supported desktop operating systems

Accepted during Phase 0:

- **Windows:** Windows 11 on a Microsoft-supported release;
- **macOS:** macOS 14 Sonoma or later;
- **Linux:** Ubuntu 24.04 LTS or later is the initial officially supported Linux baseline.

Windows 10 may be tested for temporary compatibility when required by a pilot customer, but it is not part of the officially supported production baseline.

Other Linux distributions may work when compatible with the desktop runtime, but they are initially treated as best-effort support unless explicitly added to the supported matrix later.

The supported OS matrix may be revised in future releases without changing the architecture baseline, provided security and vendor-support requirements remain satisfied.

## Deployment modes

Accepted:

### Managed cloud

- private customer ERP database hosted by Ivadoo;
- Ivadoo is responsible for infrastructure, backups and updates;
- **OVHcloud VPS-2** is the accepted initial managed-cloud baseline for the pilot and early small managed-cloud environments;
- PostgreSQL remains self-managed initially inside the isolated customer environment;
- S3-compatible object storage is used for business files and backup artifacts;
- the OVH choice must remain replaceable without changing Ivadoo business logic.

### Customizable cloud

- development/test or test/staging/production-style environments may be provided according to the customer setup;
- responsibility is shared between Ivadoo and the customer for extensions.

### On-premise

- the ERP database is hosted by the customer;
- mobile access may use a local API or controlled tunnel;
- the customer is responsible for its server while Ivadoo retains responsibility for licensing/support within the agreed contract.

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

## Managed cloud provider decision

Accepted separately during Phase 0 through issue #8 and ADR 0009:

- OVHcloud VPS-2 is the initial provider baseline;
- the choice is operational, not a permanent architecture lock-in;
- PostgreSQL + S3-compatible storage remain the portability boundaries;
- latency, operations, SLA, capacity, residency and pricing are explicit re-evaluation triggers.

See `docs/deployment/managed-cloud-evaluation.md` and `docs/adr/0009-ovh-vps2-initial-managed-cloud.md`.

## Not decided by this baseline

The following are intentionally not selected here unless separately accepted:

- server-side application framework;
- mobile application framework;
- managed database vendor for a future managed-database topology;
- queue or realtime implementation;
- reverse proxy;
- final observability stack among the tools listed as possible in the specification.

These choices require explicit decisions when they become necessary.
