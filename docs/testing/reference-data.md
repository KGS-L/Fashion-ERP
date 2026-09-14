# Foundation reference data

Phase 1 includes a deterministic, synthetic reference dataset used only for validation and integration tests.

## Profiles

The management command is:

`python manage.py seed_foundation_reference --database <alias> --profile <profile>`

Supported profiles:

- `pilot` — creates the main Foundation validation organization;
- `isolation` — creates a second organization intended for a physically separate tenant database.

## Pilot profile

The pilot profile creates:

- one Organization;
- one Company;
- two Establishments:
  - workshop;
  - store;
- one synthetic test currency (`XTS`);
- one configurable unit (`metre`);
- three synthetic users:
  - Organization administrator;
  - Company-scoped reader;
  - Establishment-scoped reader;
- scoped grants required by Foundation integration tests.

All email addresses use the reserved `.test` domain.

The command uses a known test-only password:

`Foundation-Test-Password-42!`

This password is deliberately limited to the reference dataset and must never be reused in staging or production.

## Isolation profile

The isolation profile creates:

- a different Organization;
- one Company;
- one Establishment;
- one synthetic user.

It is intended for the second PostgreSQL database used by isolation tests.

## Reproducibility

The command is idempotent for the expected reference profile. Re-running it updates deterministic records instead of creating duplicate organizations, companies, sites, users, roles or grants.

The command refuses to overwrite a database already bound to a different Organization slug.

## Data separation

This dataset is not a customer pilot dataset and contains no real personal data.

Future real pilot/customer imports must use separate provisioning/import procedures and must not depend on these reference credentials or identifiers.
