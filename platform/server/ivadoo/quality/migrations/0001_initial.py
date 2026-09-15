import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def add_quality_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    permissions = (
        ("quality.inspection.view", "inspection.view", "View quality inspections"),
        ("quality.inspection.manage", "inspection.manage", "Create quality inspections"),
        ("quality.inspection.complete", "inspection.complete", "Complete quality inspections"),
        ("quality.rework.manage", "rework.manage", "Manage quality rework"),
        ("quality.metrics.view", "metrics.view", "View quality aggregates"),
    )
    for code, action, name in permissions:
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "quality", "action": action, "name": name},
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("authorization", "0003_add_i18n_permissions"),
        ("purchases", "0003_purchase_receipts"),
        ("manufacturing", "0003_material_flow_and_output"),
    ]

    operations = [
        migrations.CreateModel(
            name="QualityInspection",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("inspection_type", models.CharField(choices=[("receiving", "Receiving"), ("in_process", "In process"), ("final", "Final")], max_length=16)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("completed", "Completed")], default="draft", max_length=16)),
                ("decision", models.CharField(choices=[("pending", "Pending"), ("accept", "Accept"), ("reject", "Reject"), ("rework", "Rework")], default="pending", max_length=16)),
                ("blocking", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("completion_reason", models.CharField(blank=True, max_length=255)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_inspections", to="organizations.company")),
                ("completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="completed_quality_inspections", to="identity.user")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_quality_inspections", to="identity.user")),
                ("manufacturing_operation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="quality_inspections", to="manufacturing.manufacturingoperation")),
                ("manufacturing_order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="quality_inspections", to="manufacturing.manufacturingorder")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_inspections", to="organizations.organization")),
                ("output_receipt", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="quality_inspections", to="manufacturing.manufacturingoutputreceipt")),
                ("parent_inspection", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reinspections", to="quality.qualityinspection")),
                ("purchase_receipt_line", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="quality_inspections", to="purchases.purchasereceiptline")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="QualityCriterion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=64)),
                ("label", models.CharField(max_length=160)),
                ("expected_value", models.CharField(blank=True, max_length=255)),
                ("result", models.CharField(choices=[("pending", "Pending"), ("pass", "Pass"), ("fail", "Fail"), ("not_applicable", "Not applicable")], default="pending", max_length=20)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("position", models.PositiveIntegerField(default=0)),
                ("inspection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="criteria", to="quality.qualityinspection")),
            ],
            options={"ordering": ("position", "id")},
        ),
        migrations.CreateModel(
            name="QualityDefect",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(blank=True, max_length=64)),
                ("severity", models.CharField(choices=[("minor", "Minor"), ("major", "Major"), ("critical", "Critical")], max_length=16)),
                ("description", models.CharField(max_length=255)),
                ("quantity", models.DecimalField(decimal_places=4, default=Decimal("1"), max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("photo_references", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("inspection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="defects", to="quality.qualityinspection")),
            ],
            options={"ordering": ("created_at", "id")},
        ),
        migrations.CreateModel(
            name="QualityRework",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("open", "Open"), ("done", "Done")], default="open", max_length=16)),
                ("instructions", models.TextField()),
                ("result_notes", models.TextField(blank=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_reworks", to="organizations.company")),
                ("completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="completed_quality_reworks", to="identity.user")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_quality_reworks", to="identity.user")),
                ("inspection", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="rework", to="quality.qualityinspection")),
                ("manufacturing_operation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="quality_reworks", to="manufacturing.manufacturingoperation")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_reworks", to="organizations.organization")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="qualityinspection",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(purchase_receipt_line__isnull=False, manufacturing_order__isnull=True, manufacturing_operation__isnull=True, output_receipt__isnull=True)
                    | models.Q(purchase_receipt_line__isnull=True, manufacturing_order__isnull=False, manufacturing_operation__isnull=True, output_receipt__isnull=True)
                    | models.Q(purchase_receipt_line__isnull=True, manufacturing_order__isnull=True, manufacturing_operation__isnull=False, output_receipt__isnull=True)
                    | models.Q(purchase_receipt_line__isnull=True, manufacturing_order__isnull=True, manufacturing_operation__isnull=True, output_receipt__isnull=False)
                ),
                name="quality_inspection_exactly_one_context",
            ),
        ),
        migrations.AddConstraint(
            model_name="qualitycriterion",
            constraint=models.UniqueConstraint(fields=("inspection", "code"), name="quality_criterion_unique_code_inspection"),
        ),
        migrations.AddConstraint(
            model_name="qualitydefect",
            constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="quality_defect_quantity_positive"),
        ),
        migrations.RunPython(add_quality_permissions, migrations.RunPython.noop),
    ]
