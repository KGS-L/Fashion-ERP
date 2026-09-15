# Foundation internationalization

Ivadoo's Phase 1 internationalization foundation implements the requirements from section 10 of the specification without selecting a country localization.

## Languages

Initial languages:

- French (`fr`);
- English (`en`);
- Spanish (`es`);
- Portuguese (`pt`);
- Arabic (`ar`, RTL).

Foundation UI labels are stored as stable-key catalogs in `catalogs/*.json`.

A missing key falls back to French and then to the key itself.

Plural catalog entries support named plural forms. Arabic supports zero/one/two/few/many/other.

## Locale data

The server exposes locale context containing:

- effective language;
- LTR/RTL direction;
- date/number format metadata;
- Company functional currency when selected;
- Establishment timezone when selected.

The User has a language preference. Company has a language default. Establishment stores a validated IANA timezone.

## Currency

`Currency` is configurable reference data.

`Company.functional_currency` is optional because the specification does not choose a default currency.

`ExchangeRate` stores Organization-scoped dated rates. No exchange-rate provider is selected in Phase 1.

## Units

`UnitOfMeasure` is configurable per Organization and stores category, conversion ratio to the category base unit and rounding.

No country-specific or textile-specific conversion list is hardcoded into the core.

## Country localizations

Tax and accounting localization remains separate under ADR 0007.

The first country/localization is still an open project decision in the specification.

## Deferred entities

Customer and Supplier do not exist in Phase 1. Their language/currency preferences will connect to this same foundation when their modules are implemented.

Document-template translation is likewise connected later when the document module exists.

## API boundary

The Foundation exposes internationalization resources under `/api/v1/i18n/`.

Language/catalog/context reads are available to authenticated users.

Currency, dated-rate and unit reference management uses:

- `foundation.i18n.view`;
- `foundation.i18n.manage`.

International-setting mutations are written to the immutable audit journal.
