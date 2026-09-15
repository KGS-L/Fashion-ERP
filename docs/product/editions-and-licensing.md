# Ivadoo editions and licensing decisions

Status: accepted during Phase 0 — Framing, with product-brand decision updated on 2026-09-15.

## Product name

The definitive product name is **Ivadoo**.

The canonical product domain selected by the project owner is **ivadoo.com**.

## Open-core licensing

Ivadoo follows an open-core model.

- The Community core is licensed under **LGPL-3.0-only**.
- Business, Enterprise Plus, premium modules and explicitly proprietary connectors are distributed under separate commercial/proprietary license terms.
- Interaction with Community components does not automatically place commercial components under the LGPL.
- Third-party dependencies remain governed by their own licenses.

## Edition boundaries

The functional scope remains the one defined by the project specification.

### Community

Target: small workshop or small fashion business starting with Ivadoo.

Initial limits:

- maximum **5 active internal users**;
- **1 legal company**;
- **1 establishment/site**.

The edition includes the Community functional scope defined in the specification: core platform, customers, measurements, simple orders, articles/products and basic catalogue capabilities.

### Business

Target: structured SME, brand or workshop operating several sites.

Initial limits:

- maximum **50 active internal users**;
- **1 legal company**;
- multiple establishments/sites within that company.

The edition extends Community with the Business functional scope defined in the specification, including inventory, purchasing, production, delivery, employees, CRM, expenses, multi-site operation, multilingual operation and the workshop mobile application.

### Enterprise Plus

Target: larger organizations, groups and international operations.

Initial limits:

- **no fixed product-level user cap**; user volume is contract-based;
- multiple legal companies;
- multiple establishments/sites;
- multi-country operation when the required localizations are available.

The edition adds the Enterprise Plus functional scope defined in the specification, including multi-company/country operation, accounting, consolidation, advanced PLM, advanced quality, subcontracting, BI, public/advanced API capabilities, SSO, SLA and private-server options.

## Definition of a counted user

For edition limits, an **active internal user** is an enabled account belonging to the customer organization and authorized to access internal ERP or workshop-mobile functions.

The following are not counted against the internal-user limit by default:

- final customers using the public/client portal;
- supplier portal identities when such a portal is enabled;
- Ivadoo platform administrators operating only in the Control Plane.

This distinction prevents public or external portal identities from consuming internal ERP seats.

## Clarifications of edition wording

These clarifications preserve the intent of the specification and do not introduce new product modules.

### API

The REST API is part of the platform architecture because the applications depend on it. The Enterprise Plus reference to "API" therefore means advanced/public integration capabilities such as externally issued API credentials and webhooks, not the absence of an internal API in Community or Business.

### PLM

Basic model/design capabilities needed by the fashion workflow remain available according to the roadmap. Enterprise Plus covers the advanced PLM scope rather than making every model/design capability Enterprise-only.

### Quality

Basic quality-control workflow belongs to the operational roadmap. Enterprise Plus adds advanced quality capabilities rather than making all quality control Enterprise-only.

## Review rule

The numerical limits above are initial commercial/product limits. They may be revised later through an explicit product decision without changing the architectural separation between editions.
