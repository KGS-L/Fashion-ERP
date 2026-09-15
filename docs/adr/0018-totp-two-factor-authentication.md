# ADR 0018 — TOTP two-factor authentication and secure recovery

Status: `accepted`

Decision owner: Phase 1 / issue #18.

## Context

The Ivadoo specification requires sessions, devices, 2FA, revocation and API tokens in the platform core. It also requires hashed passwords, revocable sessions, immutable audit and isolation.

The specification does not mandate a 2FA mechanism, recovery channel or external identity provider.

Phase 1 already has opaque PostgreSQL-backed Bearer sessions, scoped RBAC and immutable audit events.

## Decision

### Primary second factor

Ivadoo Foundation uses TOTP for interactive user 2FA.

TOTP is compatible with standard authenticator applications and does not require SMS, email or a third-party identity service.

The TOTP implementation uses PyOTP. The stored TOTP secret is encrypted at rest with Fernet from the cryptography package.

The encryption key is supplied through the `IVADOO_2FA_ENCRYPTION_KEY` environment variable and must not be committed as a production secret.

### Enrollment

Enrollment is a two-step flow:

1. an authenticated user re-enters their password and requests TOTP setup;
2. the API returns the generated secret and provisioning URI once;
3. the user confirms a valid current TOTP code;
4. the credential becomes active and one-time recovery codes are generated.

A pending unconfirmed credential does not make 2FA mandatory.

When enrollment is confirmed, all other active sessions are revoked. The current session is retained and marked as 2FA verified.

### Login

Password validation happens first.

When the user has confirmed TOTP:

- password-only login is rejected with `two_factor_required`;
- an invalid second factor is rejected with `invalid_two_factor`;
- a valid TOTP code permits session creation;
- a valid unused recovery code also permits session creation and is consumed atomically.

Sessions record whether the login satisfied a second factor.

### Recovery codes

Recovery codes are generated with high-entropy non-ambiguous characters.

Plain recovery codes are returned only at generation time. The database stores only HMAC-SHA256 digests.

A recovery code is one-time use.

Regeneration requires password reauthentication plus a valid TOTP code. A recovery code cannot be used to generate a fresh recovery-code set.

### Disabling 2FA

A user may disable their own 2FA only after password reauthentication and a valid second factor.

After disabling:

- the TOTP credential is deleted;
- all recovery codes are deleted;
- all other sessions are revoked;
- the current session remains active but is no longer marked 2FA verified.

### Administrator reset

A user with Organization-scope `foundation.access.manage` may reset another user's 2FA for account recovery.

The administrator must reauthenticate with their own password and, when their account has 2FA, their own second factor.

An administrator cannot use the admin-reset route on their own account.

Administrator reset deletes the target user's TOTP/recovery material and revokes all target sessions.

### Session/device management

The existing API session model remains authoritative.

Session metadata includes:

- device id and label;
- user agent;
- source IP;
- creation and last-seen timestamps;
- absolute and idle expirations;
- whether 2FA was verified.

Users can revoke an individual own session or all other own sessions. They cannot enumerate or revoke another user's session through personal endpoints.

### Audit

Sensitive events are written to the immutable audit journal, including setup start, enable, disable, recovery-code regeneration, session revocation and administrator reset.

TOTP secrets, raw recovery codes, passwords and Bearer tokens are never written to audit events.

## Alternatives not selected

### SMS/email OTP

Not selected in Phase 1 because the specification only marks email/SMS/push as future integrations and no trusted recovery channel is defined.

### WebAuthn/passkeys

Not selected as the initial Foundation mechanism because the specification only requires 2FA and does not define passkey/browser/native-device policy yet. It can be added later without replacing the server-side session model.

### External identity/SSO

Enterprise Plus SSO remains separate from the local Foundation authentication flow.

## Consequences

- 2FA works without an external provider;
- recovery does not introduce an unaudited bypass;
- existing sessions cannot silently bypass newly enabled 2FA;
- administrators have a controlled recovery path;
- production deployments must provision and protect a dedicated 2FA encryption key;
- later WebAuthn/SSO work can coexist with this authentication baseline.
