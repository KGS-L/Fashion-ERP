import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0001_initial"),
        ("identity", "0002_user_international_preferences"),
        ("measurements", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MeasurementSet",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.PositiveIntegerField()),
                ("measured_at", models.DateTimeField()),
                ("notes", models.TextField(blank=True)),
                ("alteration_notes", models.TextField(blank=True)),
                ("media_references", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="measurement_sets", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_measurement_sets", to="identity.user")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="measurement_sets", to="customers.customer")),
                ("establishment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="measurement_sets", to="organizations.establishment")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="measurement_sets", to="organizations.organization")),
                ("profile", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="measurement_sets", to="measurements.measurementprofile")),
            ],
            options={"ordering": ("-measured_at", "-version")},
        ),
        migrations.CreateModel(
            name="MeasurementValue",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("value", models.DecimalField(decimal_places=4, max_digits=14)),
                ("tolerance", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("note", models.TextField(blank=True)),
                ("definition", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="measurement_values", to="measurements.measurementdefinition")),
                ("measurement_set", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="values", to="measurements.measurementset")),
            ],
            options={"ordering": ("definition__name",)},
        ),
        migrations.AddConstraint(model_name="measurementset", constraint=models.UniqueConstraint(fields=("customer", "version"), name="measurement_set_unique_customer_version")),
        migrations.AddConstraint(model_name="measurementvalue", constraint=models.UniqueConstraint(fields=("measurement_set", "definition"), name="measurement_value_unique_definition_per_set")),
        migrations.AddConstraint(model_name="measurementvalue", constraint=models.CheckConstraint(condition=models.Q(("value__gte", 0)), name="measurement_value_nonnegative")),
        migrations.AddConstraint(model_name="measurementvalue", constraint=models.CheckConstraint(condition=models.Q(("tolerance__gte", 0), ("tolerance__isnull", True), _connector="OR"), name="measurement_value_nonnegative_tolerance")),
    ]
