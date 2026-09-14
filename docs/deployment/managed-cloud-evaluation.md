# Managed cloud provider evaluation

Status: `accepted` during Phase 0.

Decision date: 2026-09-14.

This document records the initial managed-cloud infrastructure choice for FashionERP without changing the portability rules already accepted in the architecture baseline.

## Non-negotiable architecture rules

The provider choice must preserve:

- one isolated ERP environment and private PostgreSQL database boundary per customer organization;
- PostgreSQL as the relational database;
- S3-compatible object storage for business files and backup artifacts;
- exportable PostgreSQL backups and portable object data;
- documented restore procedures;
- no dependency on a proprietary database model that prevents migration;
- continued support for customizable cloud, on-premise and private-server deployments.

## Accepted initial provider

FashionERP will use **OVHcloud VPS-2 as the initial managed-cloud baseline for the pilot and early small managed-cloud customers**.

This is an initial infrastructure choice, not a permanent provider lock-in.

### OVHcloud VPS-2 reference

Official OVHcloud pricing checked on 2026-09-14 lists VPS-2 from **EUR 7.21 excluding VAT per month** with:

- 4 vCores;
- 8 GB RAM;
- 75 GB NVMe storage;
- 1 Gbit/s public bandwidth;
- unlimited traffic;
- one automated daily backup representing the previous 24 hours.

The built-in one-day backup is useful for short recovery windows but **does not replace FashionERP's application-level backup policy**.

Reference: https://www.ovhcloud.com/fr/vps/unmetered-vps/

## Object storage and backup strategy

OVHcloud Object Storage is compatible with the S3 model required by FashionERP.

At the time of this decision, OVHcloud One Zone Standard Object Storage is listed at approximately **EUR 0.0070956 per GiB/month**, with external ingress/egress and API requests shown as free in the current French price list.

Planning references:

- 100 GiB: approximately EUR 0.71/month;
- 250 GiB: approximately EUR 1.77/month;
- 1 TiB: approximately EUR 7.27/month.

Reference: https://www.ovhcloud.com/fr/public-cloud/prices/

FashionERP backups must therefore use two complementary layers:

1. the OVH VPS daily backup for short-term server recovery;
2. application-level PostgreSQL dumps and required business-file backup artifacts stored separately in object storage with FashionERP retention rules.

The application-level retention policy remains daily/weekly/monthly as defined by the project specification and must be tested through restore exercises.

## Initial pilot topology

For the first managed-cloud pilot:

- 1 x OVHcloud VPS-2 for the customer's isolated FashionERP environment;
- PostgreSQL self-managed inside the isolated customer environment;
- application services isolated from other customer organizations;
- customer-specific S3-compatible object-storage boundary/credentials;
- OVH daily VPS backup enabled as provided by the offer;
- PostgreSQL dumps and required backup artifacts exported to object storage;
- secrets kept outside source code;
- monitoring added progressively without changing the provider-neutral application architecture.

A planning reference using VPS-2 plus approximately 250 GiB of One Zone Standard Object Storage is about **EUR 8.98 excluding VAT per month**, before domain/email costs, observability tooling, exceptional storage growth and operational labor.

This is an infrastructure planning estimate, not a customer selling price and not a contractual OVHcloud quote.

## Business production + staging reference

A small Business environment that requires separate production and staging may start with:

- production: 1 x VPS-2;
- staging: 1 x VPS-2;
- separate PostgreSQL databases/environments;
- no unsanitized production data copied into staging;
- approximately 500 GiB combined object-storage planning allowance where justified.

Reference infrastructure floor:

- compute: approximately EUR 14.42/month for two VPS-2 instances;
- 500 GiB One Zone Standard Object Storage: approximately EUR 3.55/month;
- total planning reference: approximately **EUR 17.97 excluding VAT per month** before operational labor and additional services.

Actual sizing must be increased when workload, concurrency, storage, SLA or resilience requirements justify it. VPS-3, larger OVH infrastructure, managed PostgreSQL or a different topology remain valid later options.

## Alternatives retained

### Hetzner Cloud

Remains a valid alternative if its compute/storage economics, regions or operational characteristics become more attractive for a future customer or migration.

### DigitalOcean

Remains a valid alternative when a simpler managed-PostgreSQL operating model is worth the higher infrastructure cost.

### OVHcloud Public Cloud / managed PostgreSQL

Remains a natural upgrade path when FashionERP needs stronger managed-service guarantees, high availability, contractual SLA requirements or separation of application and database operations.

## Operational consequence

Using VPS-2 means FashionERP initially operates PostgreSQL itself. The team therefore owns:

- PostgreSQL patching and upgrades;
- database monitoring;
- backup scheduling and encryption;
- backup retention;
- restore testing;
- capacity monitoring;
- incident recovery procedures.

This operational burden is accepted for the pilot because the cost is low and the stack remains portable.

## Re-evaluation triggers

The choice must be reviewed when one of the following becomes true:

- measured latency from Burkina Faso is not acceptable for real pilot usage;
- self-managed PostgreSQL creates excessive operational or recovery risk;
- managed-database or high-availability requirements become mandatory;
- Enterprise Plus SLA requirements exceed a single-VPS topology;
- data-residency or contractual requirements require another region/provider;
- OVHcloud pricing or product conditions change materially;
- observed CPU, RAM, disk or I/O usage exceeds the VPS-2 baseline;
- a customer requires dedicated/private infrastructure beyond the managed-cloud baseline.

## Decision

**Accepted:** OVHcloud VPS-2 is the initial managed-cloud baseline for FashionERP pilot and early small managed-cloud environments.

PostgreSQL and S3-compatible object storage remain the portability boundary. The provider choice must not be encoded into FashionERP business logic.

This decision does **not** authorize deployment automation in GitHub Actions. CI remains validation/test-only until the deployment phase is explicitly approved.
