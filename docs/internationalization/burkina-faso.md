# Burkina Faso localization baseline

Status: `accepted` during Phase 0.

Burkina Faso is the first country localization targeted by Ivadoo.

## Scope

The localization must keep Burkina Faso-specific fiscal, accounting, documentary and regulatory rules separate from the common ERP core.

The initial accounting baseline follows the OHADA / SYSCOHADA framework applicable to the country. Burkina Faso-specific requirements must be implemented in country localization modules rather than in generic sales, purchasing, inventory, manufacturing or accounting logic.

## Initial localization work

The first implementation must document and validate, before production use:

- applicable chart-of-accounts requirements and mappings;
- tax and VAT rules relevant to the pilot scope;
- invoice and document requirements;
- numbering and sequencing constraints;
- statutory accounting outputs required for the chosen pilot scope;
- electronic invoicing or certified invoicing requirements that are applicable at the time of implementation;
- currency, date, number and timezone defaults appropriate for Burkina Faso.

## Validation rule

Country-specific fiscal and accounting behavior must be verified against current official rules before it is presented as production-ready.

The common Ivadoo core must remain usable by other country localizations without embedding Burkina Faso-specific assumptions.
