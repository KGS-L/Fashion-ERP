import uuid

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("extensibility", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomFieldDefinition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("model_key", models.CharField(max_length=160)),
                (
                    "key",
                    models.CharField(
                        max_length=64,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Custom field keys must start with x_ and use lowercase letters, numbers and underscores.",
                                regex="^x_[a-z][a-z0-9_]{1,61}$",
                            )
                        ],
                    ),
                ),
                ("label", models.CharField(max_length=160)),
                (
                    "field_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("long_text", "Long text"),
                            ("integer", "Integer"),
                            ("decimal", "Decimal"),
                            ("boolean", "Boolean"),
                            ("date", "Date"),
                            ("datetime", "Datetime"),
                            ("selection", "Selection"),
                            ("multi_selection", "Multi selection"),
                            ("reference", "Reference"),
                        ],
                        max_length=24,
                    ),
                ),
                ("required", models.BooleanField(default=False)),
                ("default_value", models.JSONField(blank=True, null=True)),
                ("options", models.JSONField(blank=True, default=list)),
                ("validation", models.JSONField(blank=True, default=dict)),
                ("is_searchable", models.BooleanField(default=False)),
                ("is_reportable", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_custom_fields",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="custom_field_definitions",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"ordering": ("model_key", "key")},
        ),
        migrations.CreateModel(
            name="CustomObjectData",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("model_key", models.CharField(max_length=160)),
                ("object_id", models.UUIDField()),
                ("values", models.JSONField(blank=True, default=dict)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="custom_object_data",
                        to="organizations.organization",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="updated_custom_object_data",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="customfielddefinition",
            constraint=models.UniqueConstraint(
                fields=("organization", "model_key", "key"),
                name="extensibility_unique_custom_field",
            ),
        ),
        migrations.AddIndex(
            model_name="customfielddefinition",
            index=models.Index(
                fields=["organization", "model_key", "is_active"],
                name="ext_custom_field_lookup",
            ),
        ),
        migrations.AddConstraint(
            model_name="customobjectdata",
            constraint=models.UniqueConstraint(
                fields=("organization", "model_key", "object_id"),
                name="extensibility_unique_custom_object_data",
            ),
        ),
        migrations.AddIndex(
            model_name="customobjectdata",
            index=models.Index(
                fields=["organization", "model_key", "object_id"],
                name="ext_custom_object_lookup",
            ),
        ),
    ]
