# Identity and API sessions

This Django application owns the Phase 1 identity foundation for FashionERP.

Current responsibilities:

- project-owned UUID user model;
- password authentication through Django;
- opaque revocable API sessions stored in PostgreSQL;
- Bearer-token authentication for DRF;
- login, logout, current-user and session-management endpoints.

Out of scope here:

- 2FA enrollment and recovery (#18);
- organization/company/establishment RBAC scopes (#13);
- persistent immutable audit journal (#14);
- Enterprise Plus SSO and public API keys.
