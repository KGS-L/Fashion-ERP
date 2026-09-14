# ADR 0013 — API authentication and revocable server-side sessions

Status: `proposed`

Decision owner: Phase 1 / issue #10.

## Context

The FashionERP specification requires:

- authentication under `/api/v1/auth/`;
- hashed passwords;
- revocable sessions;
- identifiable sessions/devices;
- 2FA;
- strict authorization and organization isolation;
- desktop, mobile and server/API usage.

Issue #10 implements the base authentication and session lifecycle. Full 2FA and richer device administration remain in #18, while roles/scopes are implemented in #13 and audit persistence in #14.

The authentication mechanism must therefore provide immediate revocation and a stable foundation for device/session management without prematurely implementing SSO or Enterprise Plus API keys.

## Proposed decision

### Identity foundation

Create a project-owned Django `User` model **before the first application migration**, based on `AbstractUser`, with a UUID primary key.

The Django `username` field remains the canonical local login identifier for Phase 1, but the public API calls it `login` so clients are not coupled to Django terminology.

Email is an account attribute, not silently assumed to be the mandatory login identifier. SSO and external identities remain deferred.

### Passwords

Use Django's password framework rather than implementing password cryptography in FashionERP.

Use Argon2id as the preferred password hasher, with Django's supported hashers retained for verification/migration compatibility.

Login failures return a generic authentication error and must not reveal whether a login identifier exists.

### API sessions

Use **opaque, cryptographically random Bearer session tokens backed by PostgreSQL**, not self-contained JWT access tokens.

A session record stores:

- UUID session id;
- user;
- one-way digest of the bearer token, never the raw token;
- creation time;
- last activity time;
- absolute expiration time;
- revocation time/reason when revoked;
- client-provided device label/id when available;
- bounded user-agent metadata needed to identify the session.

The raw bearer token is returned only when the session is created.

API clients authenticate with:

`Authorization: Bearer <opaque-session-token>`

The DRF authenticator hashes the supplied token, resolves the active server-side session and rejects expired, revoked or inactive-user sessions before permissions run.

### Why opaque server-side sessions

FashionERP explicitly requires revocable sessions and device/session management. A server-side session record makes revocation effective on the next authenticated request and provides a natural object for #18.

DRF's built-in TokenAuthentication is intentionally simple and does not provide the required per-device expiry/revocation lifecycle by itself.

JWT remains useful in other architectures, but a stateless access token would complicate immediate revocation unless FashionERP adds blacklist/state checks, reducing the main benefit of stateless JWTs.

### Session lifetime

Both idle and absolute expiry are enforced server-side.

The exact timeout values are configuration, not hard-coded domain rules. Initial secure defaults will be documented in the implementation and can later become policy-driven if product requirements require different values by deployment or role.

### Phase 1 auth endpoints

Issue #10 may implement only the base lifecycle:

- `POST /api/v1/auth/login/`
- `POST /api/v1/auth/logout/`
- `GET /api/v1/auth/me/`
- `GET /api/v1/auth/sessions/`
- `POST /api/v1/auth/sessions/{uuid}/revoke/`

The sessions endpoint exposes metadata only, never token digests or raw tokens.

### Separation from later issues

#10 prepares but does not complete:

- TOTP/recovery/2FA flows — #18;
- role/module/action/company/establishment scopes — #13;
- immutable persisted security audit — #14;
- SSO — Enterprise Plus phase;
- API keys/webhooks — Enterprise Plus API work.

Security-sensitive events should expose integration points so #14 can persist audit events without redesigning authentication.

## Security rules

- bearer tokens require HTTPS outside local development/test;
- token values are never written to application logs;
- raw passwords are never logged or persisted outside Django's password framework;
- authentication errors are generic;
- session expiry and revocation are enforced server-side;
- inactive users cannot authenticate or continue using a session;
- login endpoints must support throttling/rate limiting before production exposure;
- changing credentials or security state must support invalidating relevant sessions;
- tests cover unauthenticated, invalid-token, expired, revoked and inactive-user cases.

## Consequences

- every authenticated API request performs a server-side session lookup;
- immediate revocation is straightforward;
- session/device visibility has a first-class persistence model;
- horizontal scaling remains possible because session state is in PostgreSQL rather than process memory;
- caching may later optimize validated session lookups without changing the contract;
- native desktop/mobile clients can keep the bearer secret in platform secure storage;
- browser-specific cookie transport can be added separately without changing the server-side session model.

## Alternatives considered

### DRF TokenAuthentication

Rejected as the primary FashionERP mechanism because DRF documents it as a fairly simple implementation and it does not natively model multiple expiring/revocable device sessions.

### Stateless JWT access/refresh tokens

Not selected for the Foundation baseline because FashionERP's immediate revocation and device-session requirements make server-side state desirable. A blacklist/state check would reintroduce server-side session state while increasing token lifecycle complexity.

### Django cookie sessions only

Useful for same-origin browser applications, but insufficient as the sole contract for FashionERP's Tauri desktop and mobile API clients.

## Validation

This ADR remains `proposed` until explicitly validated by the FashionERP project owner.
