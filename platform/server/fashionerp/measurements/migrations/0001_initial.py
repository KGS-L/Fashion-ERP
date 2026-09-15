import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("internationalization", "0001_initial"),
        ("organizations", "0003_international_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="MeasurementDefinition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("default_tolerance", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="measurement_definitions", to="organizations.organization")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="measurement_definitions", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="MeasurementProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("garment_type", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="measurement_profiles", to="organizations.company")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="measurement_profiles", to="organizations.organization")),
            ],
            options={"ordering": ("garment_type", "name")},
        ),
        migrations.CreateModel(
            name="MeasurementProfileItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("position", models.PositiveIntegerField()),
                ("is_required", models.BooleanField(default=True)),
                ("tolerance_override", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("instruction", models.TextField(blank=True)),
                ("definition", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="profile_items", to="measurements.measurementdefinition")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="measurements.measurementprofile")),
            ],
            options={"ordering": ("position",)},
        ),
        migrations.AddConstraint(model_name="measurementdefinition", constraint=models.UniqueConstraint(fields=("organization", "code"), name="measurement_definition_unique_code_per_org")),
        migrations.AddConstraint(model_name="measurementdefinition", constraint=models.CheckConstraint(condition=models.Q(("default_tolerance__gte", 0), ("default_tolerance__isnull", True), _connector="OR"), name="measurement_definition_nonnegative_tolerance")),
        migrations.AddConstraint(model_name="measurementprofile", constraint=models.UniqueConstraint(fields=("organization", "code"), name="measurement_profile_unique_code_per_org")),
        migrations.AddConstraint(model_name="measurementprofileitem", constraint=models.UniqueConstraint(fields=("profile", "definition"), name="measurement_profile_unique_definition")),
        migrations.AddConstraint(model_name="measurementprofileitem", constraint=models.UniqueConstraint(fields=("profile", "position"), name="measurement_profile_unique_position")),
        migrations.AddConstraint(model_name="measurementprofileitem", constraint=models.CheckConstraint(condition=models.Q(("tolerance_override__gte", 0), ("tolerance_override__isnull", True), _connector="OR"), name="measurement_profile_nonnegative_tolerance")),
    ]
