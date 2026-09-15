import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def add_return_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    permissions = (
        ("delivery.return.view", "return.view", "View delivery returns and exchanges"),
        ("delivery.return.manage", "return.manage", "Record delivery returns and exchanges"),
    )
    for code, action, name in permissions:
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "delivery", "action": action, "name": name},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("delivery", "0001_initial"),
        ("authorization", "0003_add_i18n_permissions"),
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeliveryReturn",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.CharField(max_length=64)),
                ("reason", models.TextField()),
                ("resolution", models.CharField(choices=[("return_only", "Return only"), ("exchange", "Exchange")], default="return_only", max_length=24)),
                ("idempotency_key", models.CharField(max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="delivery_returns", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_delivery_returns", to="identity.user")),
                ("delivery", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="returns", to="delivery.delivery")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="delivery_returns", to="organizations.organization")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="DeliveryReturnLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("disposition", models.CharField(choices=[("restock", "Restock"), ("quarantine", "Quarantine"), ("damaged", "Damaged")], max_length=24)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("delivery_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="return_lines", to="delivery.deliveryline")),
                ("delivery_return", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="delivery.deliveryreturn")),
                ("destination_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="delivery_return_lines", to="inventory.stocklocation")),
            ],
            options={"ordering": ("created_at", "id")},
        ),
        migrations.CreateModel(
            name="DeliveryReturnStockAllocation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("damage_movement", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="delivery_return_damage_allocation", to="inventory.stockmovement")),
                ("delivery_issue_movement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="delivery_return_source_allocations", to="inventory.stockmovement")),
                ("return_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_allocations", to="delivery.deliveryreturnline")),
                ("return_movement", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="delivery_return_allocation", to="inventory.stockmovement")),
            ],
            options={"ordering": ("created_at", "id")},
        ),
        migrations.AddConstraint(
            model_name="deliveryreturn",
            constraint=models.UniqueConstraint(fields=("organization", "number"), name="delivery_return_unique_number_org"),
        ),
        migrations.AddConstraint(
            model_name="deliveryreturn",
            constraint=models.UniqueConstraint(fields=("organization", "idempotency_key"), name="delivery_return_unique_idempotency_org"),
        ),
        migrations.AddConstraint(
            model_name="deliveryreturnline",
            constraint=models.UniqueConstraint(fields=("delivery_return", "delivery_line"), name="delivery_return_unique_delivery_line"),
        ),
        migrations.AddConstraint(
            model_name="deliveryreturnline",
            constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="delivery_return_line_quantity_positive"),
        ),
        migrations.AddConstraint(
            model_name="deliveryreturnstockallocation",
            constraint=models.UniqueConstraint(fields=("return_line", "delivery_issue_movement"), name="delivery_return_unique_source_movement"),
        ),
        migrations.AddConstraint(
            model_name="deliveryreturnstockallocation",
            constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="delivery_return_allocation_quantity_positive"),
        ),
        migrations.RunPython(add_return_permissions, migrations.RunPython.noop),
    ]
