# ADR 0019 — Module Registry and runtime capability gates

Status: `accepted`

Decision owner: platform extensibility / issue #140.

## Context

The FashionERP specification requires that each domain can be installed, activated and updated. It also requires an open-core product with Community, Business and Enterprise Plus capabilities while keeping business data traceable and secure.

Django applications and database migrations are deployment-time code/schema concerns. Allowing a customer administrator to dynamically uninstall Python packages or reverse arbitrary schema migrations at runtime would make upgrades, audit and referential integrity unsafe.

The existing Phase 1/2 modules are already deployed in the server package and must stay available by default so the new registry does not retroactively disable merged behavior.

## Decision

FashionERP separates **code availability** from **organization capability activation**.

### Code manifest

Every deployable domain registers a static `ModuleManifest` containing:

- stable module code;
- product name/version;
- dependencies;
- required/default-enabled flags;
- edition metadata;
- API prefixes owned by the module.

The code manifest is version controlled and changes with a FashionERP release.

### Organization installation state

`ModuleInstallation` stores the organization-local state and installed code version. Activation/deactivation never deletes business rows.

A module can be enabled only if its dependencies are enabled. A module cannot be disabled while enabled dependants require it. Required foundation modules cannot be disabled.

### Server-side enforcement

A disabled module must not remain callable through a hidden URL. Opaque Bearer authentication therefore applies a registry gate after resolving the authenticated organization and before the business view executes. Paths owned by a disabled module return a permission failure.

UI visibility, desktop menus and future license screens are secondary projections of the same server-side state, not security controls.

### Deployment and updates

Installing new Python code and applying Django migrations remain release/deployment operations. The registry does not execute arbitrary packages, Python hooks or schema changes uploaded by a tenant.

A deployed module version can be activated for an organization only when its code manifest exists in that release. Phase 6 Control Plane/licensing will consume this registry rather than creating a parallel module inventory.

## Consequences

- existing Phase 2 domains are default-enabled;
- future modules can ship disabled until licensed/configured;
- deactivation preserves history and supports later reactivation/downgrade rules;
- module dependencies become machine-readable;
- server APIs can enforce activation consistently;
- schema migration safety remains under release control.

## Deferred

This ADR does not yet define entitlement enforcement, subscription billing, marketplace installation, hot-loading third-party Python code or the final Control Plane synchronization protocol. Those remain Phase 6 concerns.
