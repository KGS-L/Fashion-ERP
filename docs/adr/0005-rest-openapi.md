# ADR-0005 — REST API with OpenAPI documentation

Status: `accepted`

## Context
Desktop, mobile and other approved interfaces require a stable application boundary with permissions enforced server-side.

## Decision
Use a versioned REST API beginning at `/api/v1`, documented with OpenAPI. Lists support pagination, filtering, sorting and search where applicable, and authorization is enforced by the API.

## Consequences
- clients depend on explicit API contracts rather than database access;
- OpenAPI must track implemented interfaces;
- permission tests are required at the API boundary;
- Enterprise Plus API keys/webhooks remain advanced capabilities and are not confused with the internal REST API baseline.

## Alternatives
No GraphQL-first or direct-database client architecture is part of the current baseline.
