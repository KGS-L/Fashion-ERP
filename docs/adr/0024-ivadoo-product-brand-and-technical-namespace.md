# ADR 0024 — Ivadoo product brand and stable technical namespace

Status: `accepted`

Decision date: 2026-09-15.

Decision owner: project owner / product naming decision.

## Context

The functional and technical specification originally framed the project under the working name **Ivadoo** and explicitly left the definitive product name and brand as a decision to confirm.

The project owner has selected **Ivadoo** as the definitive public product name and **ivadoo.com** as the canonical product domain.

The implementation already contains a mature Django package namespace (`ivadoo`), migration history, environment-variable names and other technical identifiers created before the final brand decision. Renaming these identifiers only for branding would create avoidable compatibility and migration risk without changing product behavior.

## Decision

### Public product identity

The public product brand is **Ivadoo**.

New user-facing and product-facing surfaces use Ivadoo, including:

- product documentation and current project README files;
- API title and descriptive metadata;
- desktop and future client application labels;
- support and security documentation;
- authenticator issuer defaults;
- future commercial and deployment-facing product references.

The canonical product domain is **ivadoo.com**.

### Legacy source references

The original functional and technical specification remains an authoritative requirements source even where it still uses the Ivadoo name. In historical specifications, issues, commits and accepted records, Ivadoo is treated as the legacy working name for the product now branded Ivadoo.

Historical records are not rewritten solely to erase the former name.

### Stable technical namespace

The rebrand does **not** rename existing compatibility-sensitive technical identifiers by itself.

The following remain unchanged for now:

- the Python/Django package namespace `ivadoo`;
- existing Django application labels and migration history;
- stable database/application identifiers already encoded in migrations or operational configuration;
- existing `IVADOO_*` environment-variable keys;
- other persisted identifiers whose rename would require a compatibility migration.

These identifiers are implementation details and do not define the current public product name.

### New user-facing defaults

Where a value is presentation-facing rather than a compatibility key, the Ivadoo name is used. In particular:

- the default TOTP authenticator issuer becomes `Ivadoo` while the environment key remains `IVADOO_TOTP_ISSUER`;
- OpenAPI title and description use Ivadoo;
- Python distribution metadata may use the Ivadoo product name while continuing to package the `ivadoo` module namespace.

### Repository name

This ADR does not rename the GitHub repository slug `KGS-L/Ivadoo`. A repository rename is a separate operational decision because it changes clone/remotes and external references.

## Consequences

- users and new documentation see one definitive brand: Ivadoo;
- the rebrand does not require database migrations or changes to Django migration history;
- deployed environments can keep existing configuration keys during the transition;
- internal `ivadoo` references may remain visible to developers without implying that Ivadoo is still the product brand;
- historical source documents remain traceable and continue to support requirement decisions;
- any future internal namespace migration must have its own compatibility plan and explicit decision before implementation.
