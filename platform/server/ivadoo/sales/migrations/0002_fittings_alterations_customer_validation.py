import uuid

import django.db.models.deletion
from django.db import migrations, models


def add_fitting_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    permissions = (
        ("fashion.fitting.view", "fitting.view", "View fittings, alterations and customer validations"),
        ("fashion.fitting.manage", "fitting.manage", "Manage fitting sessions"),
        ("fashion.alteration.manage", "alteration.manage", "Manage customer alteration requests"),
        ("fashion.customer_validation.manage", "customer_validation.manage", "Record customer validation"),
    )
    for code, action, name in permissions:
        Permission.objects.update_or_create(code=code, defaults={"module": "fashion", "action": action, "name": name})


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0001_initial"),
        ("quality", "0001_initial"),
        ("manufacturing", "0003_material_flow_and_output"),
        ("authorization", "0003_add_i18n_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="FittingSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("scheduled_at", models.DateTimeField()),
                ("performed_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("scheduled", "Scheduled"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="scheduled", max_length=16)),
                ("result", models.CharField(choices=[("pending", "Pending"), ("fit_ok", "Fit accepted"), ("alteration_required", "Alteration required")], default="pending", max_length=24)),
                ("requires_customer_validation", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fitting_sessions", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_fitting_sessions", to="identity.user")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fitting_sessions", to="sales.order")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fitting_sessions", to="organizations.organization")),
            ],
            options={"ordering": ("-scheduled_at", "-created_at")},
        ),
        migrations.CreateModel(
            name="AlterationRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("reason", models.TextField()),
                ("adjustment_notes", models.TextField(blank=True)),
                ("priority", models.CharField(choices=[("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")], default="normal", max_length=16)),
                ("status", models.CharField(choices=[("open", "Open"), ("in_progress", "In progress"), ("done", "Done"), ("cancelled", "Cancelled")], default="open", max_length=16)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="alteration_requests", to="organizations.company")),
                ("completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="completed_alteration_requests", to="identity.user")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_alteration_requests", to="identity.user")),
                ("fitting", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="alterations", to="sales.fittingsession")),
                ("manufacturing_operation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="alteration_requests", to="manufacturing.manufacturingoperation")),
                ("manufacturing_order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="alteration_requests", to="manufacturing.manufacturingorder")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="alteration_requests", to="sales.order")),
                ("order_line", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="alteration_requests", to="sales.orderline")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="alteration_requests", to="organizations.organization")),
                ("quality_defect", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="alteration_requests", to="quality.qualitydefect")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="CustomerValidation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("decision", models.CharField(choices=[("approved", "Approved"), ("rejected", "Rejected")], max_length=16)),
                ("customer_name", models.CharField(blank=True, max_length=160)),
                ("notes", models.TextField(blank=True)),
                ("evidence_reference", models.CharField(blank=True, max_length=500)),
                ("validated_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="customer_validations", to="organizations.company")),
                ("fitting", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="customer_validation", to="sales.fittingsession")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="customer_validations", to="sales.order")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="customer_validations", to="organizations.organization")),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="recorded_customer_validations", to="identity.user")),
            ],
            options={"ordering": ("-validated_at", "-created_at")},
        ),
        migrations.RunPython(add_fitting_permissions, migrations.RunPython.noop),
    ]
