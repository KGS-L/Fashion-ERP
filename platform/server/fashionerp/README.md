# Django project package

This package contains the server-level Django configuration for Ivadoo.

The directory/package name `fashionerp` is retained as a stable internal technical namespace for compatibility with existing imports, Django application labels and migration history. It is not the current public product name.

This package owns project settings, root URL routing and ASGI/WSGI entrypoints. Business-domain code must remain modular and must not be accumulated in this package.
