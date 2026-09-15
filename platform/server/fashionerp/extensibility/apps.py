from django.apps import AppConfig


class ExtensibilityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fashionerp.extensibility"

    def ready(self):
        # Static manifests describe code capabilities. Per-organization state is
        # stored separately in ModuleInstallation.
        from . import defaults  # noqa: F401
