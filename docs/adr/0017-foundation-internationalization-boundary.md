# ADR 0017 — Foundation internationalization boundary

Status: `accepted`

Decision owner: Phase 1 / issue #15.

## Context

The Ivadoo specification requires:

- initial languages: French, English, Spanish, Portuguese and Arabic;
- translations by keys, plurals, formats and documents;
- language by user, company and customer;
- functional currency by company, customer/supplier currencies and dated rates;
- timezone by establishment;
- configurable units and number formats;
- no hardcoded business text in concerned interfaces;
- country fiscal/accounting localizations separated from the common ERP core.

The server baseline is Django 5.2 LTS and already has `USE_I18N`, `USE_TZ` and `LocaleMiddleware`.

The desktop application is specified as Tauri + Owl/TypeScript but its real Foundation UI scaffold is not yet implemented on the current Phase 1 branch.

## Decision

### Supported languages

The Foundation language set is restricted to the five languages required by the specification:

- `fr`;
- `en`;
- `es`;
- `pt`;
- `ar`.

French remains the server fallback because that is the existing project setting. Arabic is exposed as right-to-left.

### Translation keys

Foundation UI text lives in language catalog files under:

`ivadoo/internationalization/catalogs/`

Business/UI code consumes stable keys rather than embedding translated labels.

Catalog values may be simple strings or plural-form maps. Missing keys fall back first to the French catalog and then to the key itself, so a missing translation remains visible and diagnosable rather than failing the interface.

The catalog API exposes the selected language, text catalog, direction and locale format metadata. The future Owl/TypeScript UI must consume this contract rather than duplicating Foundation business labels.

### Preference hierarchy

The data model represents:

- language preference on User;
- default language on Company;
- timezone on Establishment;
- functional currency on Company.

For an authenticated interface, the explicit user preference is authoritative. Company language remains available for company-level defaults and future document/customer workflows.

Customer language and customer/supplier currency are deferred until those entities exist in Phase 2. The schema must connect them to the same internationalization primitives rather than create a parallel system.

### Currency and exchange rates

Currency is configurable reference data identified by a three-letter uppercase code.

Ivadoo does not seed an arbitrary default currency in Phase 1 because the specification does not select one.

A Company may reference one functional currency.

Exchange rates are Organization-scoped and dated. A currency pair can have one rate per date. The model does not embed a rate provider or country-specific fiscal rule.

### Units

Units of measure are Organization-scoped configurable reference data with:

- code;
- name and symbol;
- category;
- ratio to the category base unit;
- rounding precision;
- active state.

No country-specific unit policy is embedded in the common core.

### Formats and timezones

Django's locale format data is used on the server for localized date/number rendering and format metadata.

Establishment timezones use IANA timezone names and are validated through Python's standard `zoneinfo` support.

### Country localization boundary

This ADR does not change ADR 0007.

Tax, accounting, legal-document and regulatory rules remain outside the common internationalization core and must live in country localization modules.

## Consequences

- the five required languages are representable now;
- language changes do not require changes to business logic;
- Arabic layout direction is explicit;
- Company functional currency and dated rates are representable without choosing a country;
- Establishment timezone is explicit and validated;
- units are configurable without hardcoding textile-specific conversions into the core;
- future Customer/Supplier and document modules have a defined integration point;
- no new third-party i18n dependency is introduced.

## Deferred

Phase 1 does not implement:

- a complete country fiscal/accounting localization;
- a default currency or initial currency list;
- customer/supplier language/currency fields before those entities exist;
- final document-template translation before the document module exists;
- desktop rendering code before the Tauri + Owl Foundation UI scaffold exists.

These are integration points, not permission to hardcode country rules into the common core.
