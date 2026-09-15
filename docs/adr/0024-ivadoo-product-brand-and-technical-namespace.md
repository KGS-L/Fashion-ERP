# ADR 0024 — Ivadoo product identity and complete technical namespace

Status: `accepted`

Decision date: 2026-09-15.

Decision owner: project owner / product naming decision.

## Context

The functional and technical specification was created before the definitive product brand was selected. It explicitly left the final product name and brand as a decision to confirm.

The project owner selected **Ivadoo** as the definitive product name and **ivadoo.com** as the canonical product domain. Because the product is still in active development and has not reached its first production release, the owner subsequently requested that the rename be completed across both public surfaces and current technical identifiers before Phase 3 continues.

A partial rebrand would leave two identities in source code, configuration, database helper identifiers, documentation and developer tooling. That would create needless long-term compatibility debt before the product is released.

## Decision

Ivadoo is the single current product and technical identity for the project.

### Public product identity

New and current user-facing surfaces use **Ivadoo**, including:

- product documentation and project README files;
- API title and descriptive metadata;
- desktop and future client application labels;
- support and security documentation;
- authenticator issuer defaults;
- commercial and deployment-facing product references.

The canonical product domain is **ivadoo.com**.

### Python and Django namespace

The server package namespace is **`ivadoo`**.

Current Django imports, application configuration, root URL configuration, ASGI/WSGI entrypoints, authentication paths and package metadata use that namespace. Django application labels such as `identity`, `organizations`, `audit`, `catalog` and `sales` remain unchanged so the logical migration graph and database table naming stay stable.

### Configuration namespace

Project-owned environment variables use the **`IVADOO_*`** prefix. Current database defaults, CI fixtures, OpenAPI artifact names and operational examples use Ivadoo naming as well.

This is a pre-release configuration rename. Environments created during development must update their local configuration to the new keys before running the renamed server.

### Database identifiers

Brand-specific PostgreSQL helper identifiers owned by the application use the `ivadoo_` prefix. A forward compatibility migration renames previously created audit trigger/function identifiers when upgrading an existing development database, while a fresh database creates only the Ivadoo identifiers.

Business table names and Django app labels are not renamed because they do not contain the product brand.

### Historical records

Published Git history, already-closed GitHub discussions and the original source specification are historical records and are not rewritten. Their terminology does not define the current codebase identity.

Current tracked source files, current documentation and active configuration must use Ivadoo naming. CI contains a repository-level guard that rejects reintroduction of the superseded product identifier in tracked paths or text.

### Repository metadata

The GitHub repository itself is expected to use the Ivadoo name and description. Renaming the repository slug is an operational GitHub setting rather than an application-code migration; after the repository is renamed, developer remotes should point to the new canonical repository URL.

## Consequences

- Ivadoo has one product identity across user-facing and developer-facing surfaces;
- the Python package becomes `ivadoo` and project environment variables become `IVADOO_*`;
- existing development environments must update configuration keys;
- existing development databases receive a compatibility migration for brand-specific audit identifiers;
- Django business app labels and migration numbering remain stable;
- the repository naming guard prevents accidental reintroduction of the superseded identifier;
- Phase 3 implementation resumes only after this rename gate and its backend/repository CI checks pass.
