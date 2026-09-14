# Foundation migrations and recovery

Status: `accepted` for Phase 1.

This document defines the operating contract for FashionERP Foundation database migrations.

The FashionERP specification requires versioned database migrations, development/test/staging/production environments, a backup before migration, documented compatibility, rollback or restoration, and periodic restoration testing. This document applies those requirements to the Django/PostgreSQL Foundation baseline.

## Source of truth

Django migration files committed under each Foundation application are the schema history.

Current Foundation migration owners are:

- `identity`;
- `organizations`;
- `authorization`;
- `audit`;
- `internationalization`.

Migration files are immutable release artifacts once they have reached a shared environment. A released migration must not be rewritten to change history; a new numbered migration must correct it.

## Versioning rules

Foundation migrations must:

- use Django's explicit numeric migration names such as `0001_initial`, `0002_...`;
- form one unambiguous leaf per Foundation application;
- declare dependencies explicitly;
- avoid hidden schema changes outside migrations;
- keep custom SQL reversible when a safe reverse operation exists;
- keep data migrations idempotent where practical;
- be reviewed together with the model/code change they support.

CI runs `makemigrations --check --dry-run` so model drift without a committed migration fails validation.

## Current Phase 1 history

### organizations

- `0001_initial` — private Data Plane Organization singleton;
- `0002_company_establishment` — Company and Establishment hierarchy and constraints;
- `0003_international_settings` — Company language/functional currency and Establishment timezone.

### identity

- `0001_initial` — UUID User and revocable API sessions;
- `0002_user_organization` — User → Organization ownership;
- `0003_user_language_code` — user interface language preference;
- `0004_two_factor_security` — TOTP credential, recovery codes and session security metadata.

### authorization

- `0001_initial` — permission catalog, roles, groups, scoped grants and initial Foundation permissions;
- `0002_add_audit_permission` — audit journal read permission;
- `0003_add_i18n_permissions` — international settings permissions.

### internationalization

- `0001_initial` — currencies, dated exchange rates and configurable units.

### audit

- `0001_initial` — append-only audit journal, indexes and PostgreSQL mutation-rejection trigger.

## Environment progression

The same committed migration graph is used in:

1. development;
2. test/CI;
3. staging;
4. production.

Environment-specific schema forks are not permitted.

A migration that has not succeeded in test/CI must not be promoted. Staging should use a production-like database engine/version and representative data volume before production rollout.

## Pre-migration procedure

Before changing a staging or production database:

1. verify application version and expected migration target;
2. run `python manage.py makemigrations --check --dry-run`;
3. inspect `python manage.py migrate --plan`;
4. verify that the database backup policy is healthy;
5. create a fresh PostgreSQL backup immediately before the migration;
6. record the backup identifier/location and application revision;
7. confirm available maintenance window when the migration may lock or rewrite tables;
8. apply migrations with the exact release artifact.

The backup itself is an operational/storage responsibility and is not implemented by this issue.

## Apply and verify

Standard apply:

`python manage.py migrate --noinput`

After apply:

`python manage.py migrate --check`

The release must also run application health checks and targeted business/security smoke tests appropriate to the changed schema.

For a private Data Plane topology, every customer database must reach the same compatible migration target for the deployed application version.

## Rollback decision

A rollback is not automatically equivalent to running a reverse Django migration.

Use one of two paths.

### Safe schema reverse

A reverse migration may be used only when:

- the affected operations are explicitly reversible;
- reversing does not destroy business/audit/security data that must be retained;
- the exact reverse target has been rehearsed;
- application code is rolled back to a compatible revision.

Example command:

`python manage.py migrate <app_label> <previous_migration>`

### Restore from backup

Restore is the required path when:

- a migration is destructive or semantically irreversible;
- data was transformed and cannot be reconstructed safely;
- a failed migration left the database in an uncertain state;
- cross-application rollback would violate integrity;
- audit/security history would be compromised by reverse operations.

Production recovery must restore the pre-migration PostgreSQL backup and deploy the matching application revision.

The specification also requires periodic restoration testing; that operational rehearsal is tracked separately from the schema migration implementation.

## Failed migration procedure

If a migration fails:

1. stop further rollout;
2. preserve database/application logs and the failing revision;
3. do not use `--fake` to bypass the failure unless a reviewed recovery procedure explicitly requires it;
4. determine whether Django/PostgreSQL transaction handling rolled back the migration completely;
5. verify `django_migrations` and actual schema state;
6. if state is clean, fix with a new migration and rehearse again;
7. if state is uncertain or data may be damaged, restore the pre-migration backup;
8. rerun validation in staging before attempting production again.

## CI contract

CI remains test-only and does not deploy.

It validates:

- model/migration drift;
- migration graph conflicts;
- one Foundation leaf per application;
- explicit versioned migration names;
- no operation marked irreversible without an explicit policy change;
- migration plan generation;
- forward migration from an empty PostgreSQL database;
- the same forward migration on an isolated tenant database;
- no unapplied migrations after migration;
- the full Django test suite.

This proves that an empty database can reproducibly reach the current Foundation schema.

## Compatibility record

The current Foundation runtime baseline is:

- Python 3.14;
- Django 5.2 LTS;
- PostgreSQL as the required database engine.

The exact production PostgreSQL version and backup/restore automation remain governed by the dedicated PostgreSQL/storage and deployment work. CI's PostgreSQL image is a compatibility fixture, not a production-version decision.
