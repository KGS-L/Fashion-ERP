import decimal
import uuid

import django.db.models.deletion
from django.db import migrations, models


def add_operations_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    for code, action, name in (
        ("operations.approval.view", "approval.view", "View operational approvals"),
        ("operations.approval.manage", "approval.manage", "Manage operational approval rules"),
        ("operations.approval.approve", "approval.approve", "Approve operational actions"),
    ):
        Permission.objects.update_or_create(code=code, defaults={"module": "operations", "action": action, "name": name})


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("authorization", "0003_add_i18n_permissions"),
        ("identity", "0004_two_factor_security"),
        ("inventory", "0001_initial"),
        ("organizations", "0003_international_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApprovalRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("resource", models.CharField(choices=[("purchase_order", "Purchase order"), ("stock_movement", "Stock movement")], max_length=32)),
                ("action", models.CharField(max_length=64)),
                ("threshold", models.DecimalField(decimal_places=4, default=decimal.Decimal("0"), max_digits=18)),
                ("require_distinct_approver", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="operational_approval_rules", to="organizations.company")),
                ("establishment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="operational_approval_rules", to="organizations.establishment")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operational_approval_rules", to="organizations.organization")),
                ("warehouse", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="operational_approval_rules", to="inventory.warehouse")),
            ],
            options={"ordering": ("resource", "action", "-threshold")},
        ),
        migrations.CreateModel(
            name="StockMovementApproval",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("movement_type", models.CharField(max_length=32)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("payload", models.JSONField(default=dict)),
                ("payload_digest", models.CharField(max_length=64)),
                ("idempotency_key", models.CharField(blank=True, max_length=160)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled")], default="pending", max_length=16)),
                ("decision_reason", models.CharField(blank=True, max_length=255)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("consumed_movement_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movement_approvals", to="organizations.company")),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="decided_stock_movement_approvals", to="identity.user")),
                ("establishment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_movement_approvals", to="organizations.establishment")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movement_approvals", to="organizations.organization")),
                ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="requested_stock_movement_approvals", to="identity.user")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movement_approvals", to="inventory.warehouse")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(model_name="approvalrule", constraint=models.CheckConstraint(condition=models.Q(("threshold__gte", 0)), name="operations_approval_threshold_nonnegative")),
        migrations.AddConstraint(model_name="approvalrule", constraint=models.UniqueConstraint(fields=("organization", "company", "establishment", "warehouse", "resource", "action", "threshold"), name="operations_unique_approval_rule_scope", nulls_distinct=False)),
        migrations.AddConstraint(model_name="stockmovementapproval", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="operations_stock_approval_quantity_positive")),
        migrations.AddConstraint(model_name="stockmovementapproval", constraint=models.UniqueConstraint(condition=~models.Q(("idempotency_key", "")), fields=("organization", "idempotency_key"), name="operations_stock_approval_unique_idempotency_org")),
        migrations.RunPython(add_operations_permissions, migrations.RunPython.noop),
    ]
