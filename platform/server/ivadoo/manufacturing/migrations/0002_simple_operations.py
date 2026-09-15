import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def add_operation_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    permissions = (
        ("manufacturing.work_center.view", "work_center.view", "View manufacturing work centers"),
        ("manufacturing.work_center.manage", "work_center.manage", "Manage manufacturing work centers"),
        ("manufacturing.operation.view", "operation.view", "View manufacturing operations"),
        ("manufacturing.operation.manage", "operation.manage", "Plan manufacturing operations"),
        ("manufacturing.operation.transition", "operation.transition", "Transition manufacturing operations"),
        ("manufacturing.operation.override_sequence", "operation.override_sequence", "Override manufacturing operation sequence"),
    )
    for code, action, name in permissions:
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "manufacturing", "action": action, "name": name},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("manufacturing", "0001_initial"),
        ("authorization", "0003_add_i18n_permissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkCenter",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=160)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_work_centers", to="organizations.company")),
                ("establishment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_work_centers", to="organizations.establishment")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_work_centers", to="organizations.organization")),
            ],
            options={"ordering": ("company__name", "code")},
        ),
        migrations.CreateModel(
            name="ManufacturingOperation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("operation_type", models.CharField(choices=[("cutting", "Cutting"), ("sewing", "Sewing"), ("embroidery", "Embroidery"), ("dyeing", "Dyeing"), ("finishing", "Finishing"), ("other", "Other")], max_length=24)),
                ("name", models.CharField(max_length=160)),
                ("position", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("in_progress", "In progress"), ("done", "Done"), ("rework", "Rework"), ("cancelled", "Cancelled")], default="pending", max_length=16)),
                ("planned_minutes", models.PositiveIntegerField(default=0)),
                ("actual_minutes", models.PositiveIntegerField(default=0)),
                ("planned_quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("processed_quantity", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("rework_count", models.PositiveIntegerField(default=0)),
                ("notes", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_operations", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_manufacturing_operations", to="identity.user")),
                ("manufacturing_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operations", to="manufacturing.manufacturingorder")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_operations", to="organizations.organization")),
                ("work_center", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="operations", to="manufacturing.workcenter")),
            ],
            options={"ordering": ("manufacturing_order", "position", "created_at")},
        ),
        migrations.CreateModel(
            name="ManufacturingOperationTransition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("from_status", models.CharField(max_length=16)),
                ("to_status", models.CharField(max_length=16)),
                ("action", models.CharField(max_length=24)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("sequence_override", models.BooleanField(default=False)),
                ("processed_quantity", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18)),
                ("actual_minutes", models.PositiveIntegerField(default=0)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_operation_transitions", to="identity.user")),
                ("operation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="history", to="manufacturing.manufacturingoperation")),
            ],
            options={"ordering": ("occurred_at", "id")},
        ),
        migrations.AddConstraint(
            model_name="workcenter",
            constraint=models.UniqueConstraint(fields=("company", "code"), name="manufacturing_work_center_unique_code_company"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingoperation",
            constraint=models.UniqueConstraint(fields=("manufacturing_order", "position"), name="manufacturing_operation_unique_position_order"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingoperation",
            constraint=models.CheckConstraint(condition=models.Q(("planned_quantity__gt", 0)), name="manufacturing_operation_planned_quantity_positive"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingoperation",
            constraint=models.CheckConstraint(condition=models.Q(("processed_quantity__gte", 0)), name="manufacturing_operation_processed_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingoperation",
            constraint=models.CheckConstraint(condition=models.Q(("processed_quantity__lte", models.F("planned_quantity"))), name="manufacturing_operation_processed_lte_planned"),
        ),
        migrations.RunPython(add_operation_permissions, migrations.RunPython.noop),
    ]
