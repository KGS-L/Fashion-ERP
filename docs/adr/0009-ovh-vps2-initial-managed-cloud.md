# ADR 0009 — OVHcloud VPS-2 as initial managed-cloud baseline

Status: `accepted`

Date: 2026-09-14

## Context

FashionERP requires a managed-cloud option while preserving the architecture already accepted in Phase 0: private ERP data boundaries per customer organization, PostgreSQL, S3-compatible object storage and portability to customizable cloud, on-premise or private-server deployments.

The first pilot needs a low-cost infrastructure baseline without introducing a provider-specific application runtime or managed database dependency.

## Decision

Use **OVHcloud VPS-2** as the initial managed-cloud baseline for the FashionERP pilot and early small managed-cloud customers.

The initial topology uses self-managed PostgreSQL in the isolated customer environment and S3-compatible object storage for business files and backup artifacts.

The provider's one-day automated VPS backup is complementary only. FashionERP must still create application-level PostgreSQL backups and apply its own retention and restore-testing policy.

## Consequences

Positive:

- low initial infrastructure cost;
- 4 vCores and 8 GB RAM provide a practical pilot baseline;
- unlimited traffic and 1 Gbit/s public bandwidth reduce early bandwidth-cost uncertainty;
- OVHcloud offers S3-compatible object storage;
- the application remains portable because PostgreSQL and S3-compatible storage stay provider-neutral boundaries.

Negative / responsibilities:

- FashionERP operates PostgreSQL itself initially;
- the team owns patching, monitoring, backup retention and restore validation;
- a single VPS is not an Enterprise Plus high-availability architecture;
- latency from Burkina Faso must be measured during the real pilot.

## Alternatives considered

- **Hetzner Cloud**: retained as a valid alternative for future migration or customer-specific needs.
- **DigitalOcean**: retained where managed PostgreSQL and simpler operations justify higher cost.
- **OVHcloud Public Cloud / managed PostgreSQL**: retained as an upgrade path for stronger SLA, availability or managed-database requirements.

## Re-evaluation

Revisit this ADR if latency, database operations, SLA, high availability, data residency, capacity or provider pricing makes VPS-2 unsuitable.

## Related documentation

See `docs/deployment/managed-cloud-evaluation.md` for the cost and topology evaluation.
