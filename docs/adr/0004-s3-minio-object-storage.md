# ADR-0004 — S3/MinIO-compatible object storage for business files

Status: `accepted`

## Context
FashionERP stores measurements-related photos, documents and other business files while keeping structured metadata in PostgreSQL.

## Decision
Store business file bytes in S3/MinIO-compatible object storage and keep file metadata in PostgreSQL.

## Consequences
- database and object storage must be backed up together;
- sensitive files and backups require appropriate encryption and access controls;
- deployments must preserve an S3-compatible or MinIO-compatible storage path;
- metadata-to-object consistency must be testable.

## Alternatives
Storing all file bytes directly in the relational database is not part of the current baseline.
