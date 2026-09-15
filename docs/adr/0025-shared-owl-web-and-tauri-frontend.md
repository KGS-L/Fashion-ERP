# ADR 0025 — Shared Owl/TypeScript frontend for Web and Tauri

- Status: Accepted
- Date: 2026-09-15
- Related issue: #156

## Context

The Ivadoo specification names PC, web and mobile surfaces, while the validated desktop baseline already uses Tauri + Owl/TypeScript. The specification did not state whether the web ERP should be a separate application, the same frontend served in a browser, or only a set of limited public web surfaces.

Maintaining two complete ERP frontends would duplicate navigation, forms, permissions-aware rendering, metadata consumption, internationalization and business workflows. At the same time, the desktop client needs native capabilities that a normal browser cannot always provide, while public catalogue/client surfaces must remain isolated from internal ERP data.

Phase 4 introduces public/client surfaces and later depends on a clear web boundary, so this ambiguity must be closed before web-specific implementation expands.

## Decision

Ivadoo will use **one primary Owl/TypeScript ERP frontend shared between browser and desktop**.

The same frontend codebase is intended to:

- run as the authenticated ERP web application in a browser;
- be embedded by Tauri for the installable Windows/macOS/Linux desktop application;
- consume the same versioned Django REST `/api/v1` contracts;
- consume the same server-authoritative RBAC/scopes and metadata capabilities;
- share routing, modules, forms, views, translations and design-system components where appropriate.

Tauri is an additional desktop host, not a second ERP frontend. Desktop-specific functionality may be exposed behind explicit capability/adaptor boundaries for features such as local filesystem integration, printers/scanners or other OS integrations. The browser application must not depend on those native APIs to perform normal ERP operations.

## Public web surfaces

The Phase 4 catalogue and client portal are product surfaces, but they are **not equivalent to the internal ERP back-office**. They must use dedicated public/client routes, contracts and authorization boundaries so that internal data such as costs, margins, salaries, private stock details or administrative configuration cannot leak to public users.

Shared Owl/TypeScript components may be reused when useful, but public/client access must remain explicitly separated at the API and permission layers.

## Corporate marketing website

The corporate/marketing site at `ivadoo.com` is outside the ERP application boundary. It may be implemented and deployed independently (currently planned as a separate WordPress project/repository). It must not be bundled into the Tauri desktop client and must not become the runtime host of ERP business logic.

A typical target split is:

- `ivadoo.com` — marketing/corporate website;
- `app.ivadoo.com` — authenticated ERP web frontend;
- Tauri desktop — the same authenticated Owl/TypeScript ERP frontend with optional native adapters;
- public catalogue/client portal — product surfaces backed by dedicated scoped/public API contracts.

The exact public URLs/subdomains may change without invalidating this ADR.

## Authentication and security consequences

- Authentication remains server-authoritative through the existing revocable API session model.
- The browser and Tauri clients do not gain authorization by hiding UI elements; all permissions remain enforced by Django/DRF.
- Public/client routes use dedicated access rules rather than reusing privileged back-office sessions implicitly.
- Tauri native bridges must expose the minimum required capabilities and must never become an authorization bypass.
- Sensitive offline/mobile behavior is governed separately by the Phase 4 mobile decision and does not follow automatically from this web/desktop choice.

## Deployment consequences

The shared frontend can be built once from a common source tree and then delivered through different hosts:

1. static/browser assets for the web ERP;
2. the Tauri packaging pipeline for desktop;
3. public/client entry points or bundles where the implementation requires them.

Phase 6 remains responsible for final production packaging, deployment, update and distribution mechanics.

## Alternatives considered

### Separate complete Web and Desktop frontends

Rejected because it would duplicate a large amount of product UI and create long-term consistency and maintenance risk without a current business requirement.

### Desktop-only ERP with limited web surfaces

Rejected because the product is expected to expose a complete web-accessible ERP experience in addition to the installable PC application.

### Corporate WordPress site as the ERP frontend

Rejected. WordPress is a marketing/content concern and is not part of the authenticated ERP application architecture.

## Consequences

Positive:

- one primary ERP frontend codebase;
- consistent behavior across browser and desktop;
- lower maintenance cost;
- easier reuse of metadata-driven customization and internationalization;
- native desktop capabilities remain possible through explicit adapters.

Trade-offs:

- browser and Tauri differences must be isolated cleanly;
- shared code must not assume native APIs are always present;
- public/client surfaces require deliberate security boundaries even when UI components are reused.

## Follow-up

- Phase 4 public/client implementation (#82, #83) must respect the public/back-office separation in this ADR.
- Desktop-native packaging and distribution remain Phase 6 concerns.
- Mobile architecture remains a separate explicit decision in #26.
