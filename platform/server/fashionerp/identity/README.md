# Identity and API sessions

This Django application owns the Phase 1 identity and interactive authentication foundation for FashionERP.

## Responsibilities

- project-owned UUID user model;
- password authentication through Django/Argon2;
- opaque revocable API sessions stored in PostgreSQL;
- Bearer-token authentication for DRF;
- session/device listing and targeted revocation;
- TOTP two-factor authentication;
- one-time recovery codes;
- secure administrator 2FA reset;
- audit integration for security-sensitive authentication changes.

## Session/device metadata

API sessions keep device id/label, user-agent, source IP, created/last-seen time, idle/absolute expiry and whether the session was created after satisfying 2FA.

Raw Bearer tokens are never stored; only their digest is persisted.

A user may revoke one own session or all other own sessions.

## Two-factor authentication

The Foundation 2FA mechanism is TOTP.

Enrollment requires password reauthentication, followed by confirmation of a current TOTP code.

The setup secret is encrypted at rest. Production must set a dedicated Fernet key through:

`FASHIONERP_2FA_ENCRYPTION_KEY`

After confirmation, the user receives one-time recovery codes. Only HMAC digests are stored.

When 2FA is enabled, password-only login is rejected.

## Recovery and reset

A recovery code may replace TOTP for login or personal 2FA disable and is consumed on use.

Recovery-code regeneration requires a valid TOTP code; an existing recovery code cannot mint new recovery codes.

An authorized access administrator may reset another user's 2FA only after reauthenticating themselves. The reset revokes all target sessions and is immutably audited.

There is no email/SMS recovery bypass in Phase 1 because no trusted recovery channel is defined by the specification.

## Security boundaries

Passwords, raw Bearer tokens, TOTP secrets and recovery codes must never be copied into the audit journal.

The personal security endpoints only operate on the authenticated user. Cross-user recovery is restricted to the access-administration API and `foundation.access.manage`.

Enterprise Plus SSO and public API keys remain separate future capabilities.
