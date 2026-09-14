# Audit migrations

Versioned Django migrations for the immutable Foundation audit journal live in this directory.

The initial migration also installs the PostgreSQL trigger that rejects UPDATE and DELETE operations on audit events.
