# Managed cloud provider evaluation

Status: `proposal awaiting final approval` during Phase 0.

Evaluation date: 2026-09-14.

This document evaluates an initial managed-cloud provider for FashionERP without changing the portability rules already accepted in the architecture baseline.

## Non-negotiable architecture rules

The provider choice must preserve:

- one isolated ERP environment and private PostgreSQL database boundary per customer organization;
- PostgreSQL as the relational database;
- S3-compatible object storage for business files and backup artifacts;
- exportable PostgreSQL backups and portable object data;
- documented restore procedures;
- no dependency on a proprietary database model that prevents migration;
- the ability to continue supporting customizable cloud, on-premise and private-server deployments.

## Options reviewed

### Hetzner Cloud

Strengths:

- low-cost European compute;
- Germany/Finland regions for the initial European hosting strategy;
- regular-performance CPX instances suitable for moderate application workloads;
- S3-compatible Object Storage;
- simple network/firewall/API model;
- strong portability because FashionERP can run standard PostgreSQL and Docker-compatible workloads without a provider-specific runtime.

Current reference prices, excluding VAT:

- CPX22: 2 vCPU, 4 GB RAM, 80 GB disk — EUR 19.49/month;
- CPX32: 4 vCPU, 8 GB RAM, 160 GB disk — EUR 35.49/month;
- primary IPv4: EUR 0.50/month;
- server backup service: 20% of the cloud-server price;
- Object Storage: approximately EUR 4.99/month base price including 1 TB storage and 1 TB egress according to the current service pricing.

Trade-off:

Hetzner does not provide the same managed PostgreSQL offering considered in the other options. FashionERP would therefore operate PostgreSQL itself for the initial managed cloud. This lowers cost but increases operational responsibility for patching, monitoring, backup validation and recovery.

### DigitalOcean

Strengths:

- straightforward developer experience;
- European regions including Frankfurt, Amsterdam and London;
- managed PostgreSQL available;
- S3-compatible Spaces Object Storage;
- predictable pricing and simple scaling path.

Current reference prices:

- Basic Droplet 2 vCPU / 4 GiB / 80 GiB: USD 24/month;
- managed PostgreSQL starts around USD 15.15/month for 1 GiB / 1 vCPU;
- Spaces Object Storage: USD 5/month including 250 GiB storage and 1 TiB outbound transfer.

A minimal managed-database stack therefore starts around USD 44.15/month before additional backup, monitoring or redundancy costs.

Trade-off:

The operating model is easier than self-managed PostgreSQL, but the base cost per isolated customer environment is materially higher than the proposed Hetzner pilot model.

### OVHcloud

Strengths:

- strong European/France presence;
- S3-compatible Object Storage;
- managed PostgreSQL plans;
- broader production/enterprise infrastructure options;
- attractive option for customers requiring stronger managed-service guarantees or France-hosted infrastructure.

Current reference prices:

- Discovery d2-4: 2 vCore / 4 GB / 50 GB — EUR 11.44/month, positioned by OVHcloud for test/development/sandbox;
- General Purpose b3-8 compute is around EUR 31.77/month with a 12-month Savings Plan, with local storage and public IPv4 becoming separate billing lines from 1 October 2026;
- managed PostgreSQL Production DB2-2 is around EUR 51.25/month;
- standard object storage is roughly EUR 0.01095/GB/month in the current French price list.

Trade-off:

OVHcloud provides a stronger managed-service path, but a production stack with managed PostgreSQL is substantially more expensive for the first small FashionERP customers.

## Proposed initial choice

Use **Hetzner Cloud in the European region as the initial provider for the FashionERP managed-cloud pilot**.

This is a provider choice for the first operational phase, not a permanent provider lock-in.

### Small pilot / small customer reference

Recommended starting point:

- 1 x CPX22 for the private customer ERP environment;
- PostgreSQL operated inside the customer's isolated environment;
- customer-specific S3 bucket/credentials in Hetzner Object Storage;
- provider backup service enabled;
- application-level PostgreSQL dumps written to separate object storage according to the backup policy;
- one public IPv4 only where necessary.

Approximate infrastructure reference:

- compute: EUR 19.49/month;
- IPv4: EUR 0.50/month;
- provider backups: approximately EUR 3.90/month;
- Object Storage base allocation: approximately EUR 4.99/month.

Conservative reference total: **approximately EUR 28.88/month excluding VAT**, before support tooling, monitoring services, domain/email costs, exceptional traffic and operational labor.

### Business customer with production + staging

Reference starting point:

- production: 1 x CPX32;
- staging: 1 x CPX22;
- PostgreSQL private to each required environment;
- customer-specific object-storage boundaries;
- backups enabled for both compute environments;
- production data must not be copied into staging without explicit sanitization/authorization.

Approximate infrastructure reference:

- CPX32 production: EUR 35.49;
- production backup: approximately EUR 7.10;
- production IPv4: EUR 0.50;
- CPX22 staging: EUR 19.49;
- staging backup: approximately EUR 3.90;
- staging IPv4: EUR 0.50;
- Object Storage base allocation: approximately EUR 4.99.

Conservative reference total: **approximately EUR 71.97/month excluding VAT**, before monitoring/support tooling and operational labor.

These figures are planning references, not customer prices and not contractual cloud quotes.

## Enterprise Plus direction

Enterprise Plus must not be forced onto the small-customer sizing model. Depending on workload and SLA, it may use:

- larger Hetzner instances;
- dedicated-vCPU instances;
- redundant application nodes;
- a separate database topology;
- private-server deployment;
- or another provider when managed database, regional, contractual, compliance or SLA requirements justify it.

Provider migration remains possible because PostgreSQL, S3-compatible storage and standard deployment artifacts remain the portability boundary.

## Re-evaluation triggers

The provider choice must be reviewed when one of the following becomes true:

- the first real pilot provides latency measurements from Burkina Faso that are not acceptable;
- operating PostgreSQL ourselves creates excessive support or recovery risk;
- managed-database requirements become mandatory;
- Enterprise Plus SLA requirements exceed the initial provider topology;
- data-residency or contractual requirements demand another region/provider;
- the monthly infrastructure cost advantage materially changes;
- provider pricing changes substantially.

## Recommendation

Accept Hetzner as the initial managed-cloud provider for pilot and early managed-cloud customers, while keeping DigitalOcean and OVHcloud documented as migration/alternative paths.

Do not treat this recommendation as an authorization to add deployment automation to GitHub Actions. CI remains test-only until a later explicitly approved deployment phase.
