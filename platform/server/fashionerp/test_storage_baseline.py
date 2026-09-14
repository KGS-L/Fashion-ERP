from django.conf import settings
from django.db import connections
from django.test import SimpleTestCase


class FoundationStorageBaselineTests(SimpleTestCase):
    databases = "__all__"

    def test_default_database_uses_postgresql_backend(self):
        self.assertEqual(
            settings.DATABASES["default"]["ENGINE"],
            "django.db.backends.postgresql",
        )
        self.assertEqual(connections["default"].vendor, "postgresql")

    def test_isolated_tenant_database_uses_same_postgresql_backend_when_configured(self):
        if "tenant_b" not in settings.DATABASES:
            self.skipTest("tenant_b database alias is not configured")

        self.assertEqual(
            settings.DATABASES["tenant_b"]["ENGINE"],
            "django.db.backends.postgresql",
        )
        self.assertEqual(connections["tenant_b"].vendor, "postgresql")

    def test_foundation_has_no_object_storage_runtime_configuration_yet(self):
        object_storage_settings = (
            "AWS_STORAGE_BUCKET_NAME",
            "S3_BUCKET",
            "MINIO_BUCKET",
            "FASHIONERP_OBJECT_STORAGE_BUCKET",
        )
        configured = [
            name
            for name in object_storage_settings
            if hasattr(settings, name)
        ]
        self.assertEqual(
            configured,
            [],
            msg=(
                "Foundation unexpectedly gained object-storage runtime "
                f"configuration: {configured}"
            ),
        )
