# Foundation test dependencies

Ivadoo Foundation tests require PostgreSQL.

## PostgreSQL

PostgreSQL is part of the validated architecture baseline and is not replaced by SQLite in tests.

The backend configuration always uses Django's PostgreSQL backend. CI starts an ephemeral PostgreSQL service and creates:

- the primary Foundation test database;
- a second isolated tenant database used by cross-database isolation tests.

Both databases receive the same committed migration graph.

No proprietary database or managed cloud service is required to execute the Foundation test suite.

The PostgreSQL image used by CI is a compatibility fixture. The production PostgreSQL version remains an operations/deployment decision and must be recorded separately before production rollout.

## Object storage

The architecture baseline specifies S3/MinIO-compatible object storage for documents and media.

No implemented Phase 1 Foundation feature currently persists an object/document payload. Therefore #21 intentionally does **not** introduce MinIO, S3 credentials or an object-storage SDK into the Foundation test stack.

Object storage must be added to tests when the first implemented feature actually needs it. The test target should remain S3-compatible and runnable without a proprietary managed provider.

## CI scope

CI is validation/test-only. It may create ephemeral databases and other local test dependencies, but it must not:

- provision production infrastructure;
- publish artifacts as releases;
- require production secrets;
- deploy an environment.
