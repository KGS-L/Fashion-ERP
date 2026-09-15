# ADR-0003 — PostgreSQL as the primary relational database

Status: `accepted`

## Context
Ivadoo requires transactional ERP data, scoped entities, versioned migrations, backup/restore and multi-environment operation.

## Decision
Use PostgreSQL as the primary relational database for ERP data and file metadata.

## Consequences
- schema and migrations target PostgreSQL;
- backup/restore procedures must cover PostgreSQL;
- test environments must validate behavior against PostgreSQL rather than assuming a different production database;
- cloud provider selection must preserve PostgreSQL portability.

## Alternatives
No alternative relational database is part of the current baseline.
