# ADR-0007 — Modular business domains and separate country localizations

Status: `accepted`

## Context
FashionERP must support multiple business modules and international expansion without embedding country-specific fiscal/accounting rules into common ERP logic.

## Decision
Keep business domains modular and keep country localizations separate from the common ERP core. Common sales, purchasing, stock and production rules must not be rewritten for each country.

## Consequences
- country-specific fiscal, accounting, document and regulatory rules live under localization boundaries;
- module activation must preserve authorization and edition rules;
- the first country localization can be selected independently of the core architecture;
- future localizations should be testable without changing common business behavior unnecessarily.

## Alternatives
Hardcoding the first country's rules into common ERP modules was rejected.
