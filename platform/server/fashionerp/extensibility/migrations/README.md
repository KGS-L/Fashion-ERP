# Extensibility migrations

Versioned Django migrations for the FashionERP platform extensibility layer: module activation state, customization metadata and related cross-cutting platform records.

Tenant-created custom fields do **not** generate arbitrary SQL migrations; their definitions and values are stored through the controlled metadata models documented by ADR 0020.
