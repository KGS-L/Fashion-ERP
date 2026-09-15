# Third-party notices — Phase 1 Foundation

Ivadoo Community core is licensed under LGPL-3.0-only unless otherwise stated.

The Phase 1 server directly relies on the following third-party projects.

| Dependency | Role | Upstream license |
| --- | --- | --- |
| Django | Web framework | BSD-3-Clause |
| Django REST framework | REST API | BSD-3-Clause |
| drf-spectacular | OpenAPI generation | BSD-3-Clause |
| django-filter | API filtering | BSD-3-Clause |
| Psycopg | PostgreSQL driver | LGPL-3.0-only |
| psycopg-binary | Binary extra installed by Psycopg | LGPL-3.0-only |
| argon2-cffi | Password hashing support | MIT |
| PyOTP | TOTP implementation | MIT |
| cryptography | TOTP-secret encryption | Apache-2.0 OR BSD-3-Clause |
| setuptools | Build backend/tooling | MIT |

## Review result

No direct Phase 1 dependency was identified as an obvious blocker for the LGPL-3.0-only Community direction.

Permissive BSD/MIT dependencies can be redistributed subject to their attribution/license terms. Psycopg uses the same LGPL-3.0-only license family as the Community core. `cryptography` provides an Apache-2.0 OR BSD-3-Clause choice.

This engineering review does not replace legal advice.

## Distribution rule

A packaged Ivadoo distribution must preserve applicable third-party copyright/license notices shipped by its dependencies.

Before adding or upgrading a direct dependency:

1. record it in `dependency-licenses.json`;
2. update this notice when necessary;
3. review any copyleft/network-copyleft/proprietary restrictions before merge;
4. keep future commercial-only components clearly separated from the LGPL Community core.

## Sources checked for Phase 1

License metadata was checked against upstream/PyPI package metadata for the pinned Phase 1 dependency versions during the September 2026 Foundation review.
