# ADR-0002 — Private ERP database boundary per customer organization

Status: `accepted`

## Context
FashionERP targets cloud, customizable cloud, on-premise and private-server deployments while requiring strict customer isolation.

## Decision
Each customer organization has its own ERP environment and private database boundary. An organization may contain multiple legal companies and establishments inside that boundary.

## Consequences
- inter-organization isolation is a hard security requirement;
- company and establishment scopes are enforced inside the organization's ERP boundary;
- backup, restore and migration procedures operate per customer environment;
- tests must explicitly verify that one organization cannot access another organization's data.

## Alternatives
A shared business database for all customer organizations was rejected for the baseline because it does not match the specification.
