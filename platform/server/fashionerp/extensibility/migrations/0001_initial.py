import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0003_international_settings"),
        ("identity", "0004_two_factor_security"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ModuleInstallation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("module_code", models.CharField(max_length=120)),
                ("installed_version", models.CharField(max_length=32)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("installed", "Installed"),
                            ("enabled", "Enabled"),
                            ("disabled", "Disabled"),
                        ],
                        default="installed",
                        max_length=16,
                    ),
                ),
                ("installed_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "last_changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="module_installation_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="module_installations",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"ordering": ("module_code",)},
        ),
        migrations.AddConstraint(
            model_name="moduleinstallation",
            constraint=models.UniqueConstraint(
                fields=("organization", "module_code"),
                name="extensibility_unique_module_installation",
            ),
        ),
    ]
