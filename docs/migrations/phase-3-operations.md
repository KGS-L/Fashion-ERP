# Phase 3 — migrations and reproducibility

Phase 3 adds versioned migrations for inventory, purchasing, manufacturing, quality, delivery and operational approvals. CI applies the complete migration graph to both the primary PostgreSQL test database and a second isolated tenant database, then runs `migrate --check` on both databases.

## Reference data

Phase 3 does not require manually prepared database state. Authorization permissions are seeded by versioned migrations for each operational module. The reproducible business reference scenario is created programmatically by `ivadoo.api.tests_phase3_e2e.Phase3OperationalJourneyTests`; contract tests also assert that the Phase 3 RBAC permission modules exist after migration. This keeps test execution independent from developer-local fixtures.

## Sensitive migration rollback

Schema-creation migrations are reversible through Django's normal reverse migration path while no later dependent migration is applied. The inventory immutability trigger has explicit reverse SQL, so reversing `inventory.0001_initial` removes the trigger/function together with the tables. Operational approval migrations contain only schema/permission seed operations and no irreversible external side effects.

For any environment containing business data, rollback is not performed blindly. The operational procedure is: take a database backup, stop writes, verify the target migration boundary with `migrate --plan`, restore from backup when a reverse migration would lose business data, and validate stock/audit invariants before reopening writes. Production backup/restore automation remains a Phase 6 concern; Phase 3 only documents the safe migration boundary.

## CI gate

The backend workflow performs Python syntax compilation, Django checks, `makemigrations --check --dry-run`, explicit Phase 3 migration-plan inspection, migration on primary and isolated tenant PostgreSQL databases, OpenAPI validation with `--fail-on-warn`, and the full Django test suite. There is no deploy, provisioning, publish or release job in the workflow set.
