# ADR 0014 — One customer organization per ERP Data Plane database

Status: `proposed`

Decision owner: Phase 1 / issue #11.

## Context

The FashionERP specification and accepted ADRs establish that:

- each customer organization has its own ERP environment and private database;
- one organization may contain several legal companies and establishments;
- the central Control Plane manages organizations, licenses, subscriptions, installations, versions and support;
- customer business data remains in the Data Plane and is not copied to the Control Plane by default;
- strict inter-organization isolation and explicit leakage tests are mandatory.

Issue #11 must implement `Organization` without weakening ADR 0001 or ADR 0002 by silently turning the ERP database into a shared multi-tenant business database.

The current Django scaffold is a single ERP server runtime backed by one PostgreSQL connection. Introducing transparent request-time routing across many customer databases would be a new infrastructure mechanism not required by the specification for the Foundation domain model itself.

## Proposed decision

### Data Plane boundary

Treat one running FashionERP ERP Data Plane environment as bound to **exactly one customer organization database**.

The PostgreSQL connection configured for the ERP runtime is therefore the private database of that customer organization.

The Foundation must not implement a shared business database containing several customer organizations.

### Local Organization record

Keep a minimal `Organization` record inside the private ERP database as the local identity/configuration root for the Data Plane.

It contains the Foundation transverse metadata required by the specification:

- UUID;
- name;
- stable slug/code;
- status;
- created/updated timestamps;
- logical archive timestamp where applicable.

The database enforces that only one local customer organization record can exist in a Data Plane database.

This local record is not a replacement for the Control Plane organization registry. The Control Plane remains authoritative for platform concerns such as licensing, subscription, installation and support.

### Identity binding

Data Plane users and sessions belong to the local organization boundary.

The project-owned `User` model gains an explicit organization relation. `ApiSession` inherits the organization boundary through its user and must never be transferable to another customer database.

Platform administrators remain a Control Plane concern and must not gain implicit access to customer business data through this Data Plane user model.

### Organization API

The Foundation exposes the organization resource under the already specified `/api/v1/organizations/` path.

Because a Data Plane database represents one organization:

- collection reads can only return the local organization;
- detail reads can only resolve the local organization UUID;
- an unknown/different UUID returns `404`, not a cross-tenant hint;
- ordinary authenticated Data Plane requests never enumerate other customer organizations.

Organization provisioning is a bootstrap/provisioning operation, not an unrestricted tenant self-service `POST` that could create a second organization in the same ERP database.

The initial Foundation implementation may provide a deterministic management/bootstrap command for creating the local organization and its first administrator. Control Plane-driven provisioning can call the same domain service later.

### Isolation enforcement

Inter-organization isolation is primarily a **physical database boundary**, not only a queryset filter.

Application-level organization checks remain defense in depth for Foundation objects carrying an organization relation.

No API header, query parameter or request body may select an arbitrary customer database.

In particular, the Foundation does **not** introduce `X-Organization` / `tenant_id` request routing that lets a bearer token choose another organization's database.

### Cloud routing and provisioning

Mapping an incoming customer endpoint/subdomain/installation to the correct private database is an infrastructure/Control Plane responsibility and is deliberately separated from #11.

Possible future cloud implementations may use multiple Django database aliases, connection factories, separate processes/containers, or infrastructure routing, but #11 does not select one of those deployment mechanisms.

This preserves the deployment modes in the specification: managed cloud, customizable cloud, on-premise and private server.

### Tests

#11 must test both layers:

1. **Data Plane invariant**
   - a private ERP database cannot contain two local organizations;
   - users are bound to the local organization;
   - organization detail lookup for another UUID returns `404`.

2. **Physical isolation integration**
   - CI creates two independent PostgreSQL tenant databases;
   - each is migrated and bootstrapped with a different organization/user;
   - data written to tenant A is absent from tenant B and vice versa;
   - credentials/session tokens created in tenant A are rejected by tenant B.

The physical isolation test must not rely on organization filters alone.

## Why not a shared tenant table baseline

A conventional shared-database SaaS design using `organization_id` filters everywhere would contradict ADR 0002, which explicitly selected a private ERP database boundary per customer organization.

## Why not dynamic Django multi-database routing in #11

Django supports multiple databases and database routers, but cross-database relations are constrained and routing/provisioning introduces infrastructure complexity.

The FashionERP specification requires the private-database boundary, but does not require that one Django process dynamically host every tenant database. Selecting that deployment mechanism now would conflate the domain isolation decision with later cloud provisioning.

## Consequences

- the strongest tenant boundary is PostgreSQL database separation;
- a compromised/missing queryset filter cannot by itself expose another customer's business rows because those rows are not in the database;
- local Organization remains available as the root for Company, Establishment and future scoped models;
- backup, restore and migration naturally operate per organization database;
- Control Plane and Data Plane organization concepts must have an explicit synchronization contract later;
- CI needs a second tenant database for the cross-database isolation test;
- cloud tenant routing/provisioning remains a later infrastructure concern rather than being hidden inside the Foundation ORM.

## Deferred decisions

This ADR does not decide:

- the final Control Plane Django app/service structure;
- how cloud hostnames map to customer Data Plane runtimes;
- where encrypted database credentials are stored by managed-cloud provisioning;
- whether managed cloud uses one process per tenant, connection pools, dynamic aliases or another routing layer;
- SSO and Enterprise Plus identity federation.

## Validation

This ADR remains `proposed` until explicitly validated by the FashionERP project owner.
