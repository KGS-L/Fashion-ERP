from django.apps import AppConfig


class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fashionerp.identity"

    def ready(self) -> None:
        # Register drf-spectacular's authentication extension.
        from . import schema  # noqa: F401
