# FashionERP server

This directory contains the Django server runtime for the FashionERP platform.

Validated baseline:

- Python 3.14;
- Django 5.2 LTS;
- PostgreSQL;
- Django REST Framework;
- drf-spectacular;
- django-filter.

The business API is versioned under `/api/v1/`. OpenAPI is generated from the implemented API and exposed through the reserved schema/documentation routes.

This scaffold intentionally does not implement Phase 2 business modules and does not select the final authentication/session mechanism tracked by Phase 1 issue #10.

Configuration is environment-driven. Production secrets must never be committed to the repository.
