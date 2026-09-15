import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Organization",
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
                (
                    "singleton_key",
                    models.BooleanField(
                        default=True,
                        editable=False,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("archived", "Archived"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("name",),
            },
        ),
        migrations.AddConstraint(
            model_name="organization",
            constraint=models.CheckConstraint(
                condition=models.Q(("singleton_key", True)),
                name="organization_singleton_key_true",
            ),
        ),
    ]
