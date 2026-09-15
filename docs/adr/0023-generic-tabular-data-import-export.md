# ADR 0023 — Generic CSV/XLSX import/export through domain adapters

Status: `accepted`

Decision owner: platform extensibility / issue #144.

## Context

FashionERP customers must be able to migrate spreadsheets instead of re-entering master data row by row. A naive generic ORM importer would be dangerous because stock, accounting, order states and tenant scopes require domain validation and audited transitions.

## Decision

FashionERP provides a generic tabular import/export engine with an explicit adapter registry.

### Supported foundation formats

CSV UTF-8 and XLSX are supported. The foundation parser applies file/row limits and converts both formats into the same row structure.

### Explicit resources only

A model becomes importable/exportable only when a `DataResourceAdapter` registers it. The adapter declares serializer, authorized queryset, allowed import/export fields and natural identity fields. The first safe adapters are Customer and Product. Transactional resources such as stock movements, accounting entries and order workflow state are not automatically importable.

### Mapping and custom fields

The client maps spreadsheet columns to API-native field names or active `x_...` custom fields. Unknown/non-importable targets are rejected. Custom values use the same validation and permission services as interactive customization.

### Preview before commit

Every row is validated before any write. Preview returns row actions/errors without changing the database. When commit is requested, any validation error prevents the whole import. Foundation commits are atomic.

Supported modes are create, update, upsert and skip duplicates. Update/upsert requires the adapter identity fields. Persistent external IDs, import batches and controlled rollback are deliberately handled by #145.

### Domain enforcement

Native values pass through the resource's DRF serializer and scoped RBAC checks. Imports do not bulk-write business tables or bypass serializer/domain constraints. Writes and commit summaries are audited.

### Export

Exports use the same adapter's authorized queryset and can include visible custom fields. CSV and XLSX are supported. Field-level custom permissions and model scopes remain authoritative.

## Consequences

- spreadsheet migration is reusable across modules without a dangerous universal ORM writer;
- future modules opt into generic I/O explicitly and may provide stricter adapters;
- preview catches mapping/type/scope errors before mutation;
- custom fields participate in the same import/export vocabulary as metadata/Studio;
- large persistent jobs and resumable batches can be layered on in #145 without redesigning row validation.
