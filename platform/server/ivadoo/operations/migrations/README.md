# Operations migrations

Database migrations for the Phase 3 operational approval layer.

Migrations in this directory define scoped approval rules, stock-movement approval requests, their integrity constraints and the corresponding authorization permissions. They must remain deterministic and safe to apply on both the primary ERP database and isolated tenant databases.
