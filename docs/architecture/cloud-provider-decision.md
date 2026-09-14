# Managed cloud provider and cost strategy

Status: `accepted` — Phase 0.

The FashionERP specification requires the cloud provider and cost strategy to be confirmed before development.

## Decision

FashionERP will use **OVHcloud VPS-2 as the initial managed-cloud baseline for the pilot and early small managed-cloud customers**.

This decision does not change the validated deployment model: managed cloud, customizable cloud, on-premise and private server remain supported product directions.

The initial managed-cloud topology keeps the architecture portable:

- PostgreSQL remains the relational database;
- PostgreSQL is initially self-managed inside each isolated customer environment;
- business files and backup artifacts use S3-compatible object storage;
- database backups remain exportable;
- provider-specific services must not be embedded into FashionERP business logic;
- migration to another provider remains possible.

## Initial cost reference

At the time of the decision, OVHcloud lists VPS-2 from EUR 7.21 excluding VAT per month with 4 vCores, 8 GB RAM, 75 GB NVMe, 1 Gbit/s public bandwidth, unlimited traffic and an automated one-day backup.

A planning baseline using VPS-2 plus approximately 250 GiB of OVHcloud One Zone Standard Object Storage is about EUR 8.98 excluding VAT per month before operational labor and ancillary services.

These figures are planning references, not contractual customer pricing.

## Backup rule

The provider's one-day VPS backup does not replace FashionERP's own backup policy. PostgreSQL dumps and required backup artifacts must be exported to separate object storage with the project's daily/weekly/monthly retention and tested restore procedures.

## Re-evaluation

The decision must be reviewed if latency from Burkina Faso, PostgreSQL operations, SLA/high-availability requirements, capacity, data residency or provider pricing make the VPS-2 baseline unsuitable.

Detailed evaluation: `docs/deployment/managed-cloud-evaluation.md`.

ADR: `docs/adr/0009-ovh-vps2-initial-managed-cloud.md`.
