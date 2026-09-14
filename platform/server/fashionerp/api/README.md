# Server API infrastructure

This package contains cross-cutting REST infrastructure shared by FashionERP API resources.

Current responsibilities:

- `/api/v1/` URL boundary;
- standard collection pagination;
- stable API error envelope;
- OpenAPI integration through the server project.

Authentication/session implementation is intentionally deferred to issue #10. Domain endpoints will be added only by the corresponding Foundation/module issues.
