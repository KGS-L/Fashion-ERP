from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ivadoo.crm"

    def ready(self):
        from . import tracking_models  # noqa: F401
        from . import registry  # noqa: F401
