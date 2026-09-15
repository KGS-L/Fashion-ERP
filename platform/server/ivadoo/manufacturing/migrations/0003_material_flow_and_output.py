import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def add_material_flow_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    permissions = (
        ("manufacturing.material.consume", "material.consume", "Consume reserved manufacturing materials"),
        ("manufacturing.material.consume_supplemental", "material.consume_supplemental", "Consume supplemental manufacturing materials"),
        ("manufacturing.material.remnant", "material.remnant", "Record reusable manufacturing remnants"),
        ("manufacturing.order.complete", "order.complete", "Complete manufacturing order and receive output stock"),
    )
    for code, action, name in permissions:
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "manufacturing", "action": action, "name": name},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("manufacturing", "0002_simple_operations"),
    ]

    operations = [
        migrations.CreateModel(
            name="ManufacturingMaterialConsumption",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_type", models.CharField(choices=[("reserved", "Reserved material"), ("supplemental", "Supplemental material")], max_length=16)),
                ("disposition", models.CharField(choices=[("consumed", "Consumed"), ("scrap", "Scrap / loss")], default="consumed", max_length=16)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("idempotency_key", models.CharField(max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_material_consumptions", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_manufacturing_material_consumptions", to="identity.user")),
                ("lot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_consumptions", to="inventory.stocklot")),
                ("manufacturing_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="material_consumptions", to="manufacturing.manufacturingorder")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_material_consumptions", to="organizations.organization")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_consumptions", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_consumptions", to="catalog.productvariant")),
                ("requirement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="consumptions", to="manufacturing.manufacturingmaterialrequirement")),
                ("reservation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_consumptions", to="inventory.stockreservation")),
                ("source_location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_consumptions", to="inventory.stocklocation")),
                ("stock_movement", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_consumption", to="inventory.stockmovement")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_consumptions", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("created_at", "id")},
        ),
        migrations.CreateModel(
            name="ManufacturingMaterialRemnant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("idempotency_key", models.CharField(max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_material_remnants", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_manufacturing_material_remnants", to="identity.user")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_remnants", to="inventory.stocklocation")),
                ("manufacturing_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="material_remnants", to="manufacturing.manufacturingorder")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_material_remnants", to="organizations.organization")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_remnants", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_remnants", to="catalog.productvariant")),
                ("requirement", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="remnants", to="manufacturing.manufacturingmaterialrequirement")),
                ("stock_lot", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_remnant", to="inventory.stocklot")),
                ("stock_movement", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_remnant", to="inventory.stockmovement")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_remnants", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("created_at", "id")},
        ),
        migrations.CreateModel(
            name="ManufacturingOutputReceipt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_output_receipts", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_manufacturing_output_receipts", to="identity.user")),
                ("destination_location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_output_receipts", to="inventory.stocklocation")),
                ("manufacturing_order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="output_receipt", to="manufacturing.manufacturingorder")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_output_receipts", to="organizations.organization")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_output_receipts", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_output_receipts", to="catalog.productvariant")),
                ("stock_movement", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_output_receipt", to="inventory.stockmovement")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_output_receipts", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="manufacturingmaterialconsumption",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="manufacturing_consumption_quantity_positive"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingmaterialconsumption",
            constraint=models.UniqueConstraint(fields=("organization", "idempotency_key"), name="manufacturing_consumption_unique_idempotency_org"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingmaterialremnant",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="manufacturing_remnant_quantity_positive"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingmaterialremnant",
            constraint=models.UniqueConstraint(fields=("organization", "idempotency_key"), name="manufacturing_remnant_unique_idempotency_org"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingoutputreceipt",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="manufacturing_output_quantity_positive"),
        ),
        migrations.RunPython(add_material_flow_permissions, migrations.RunPython.noop),
    ]
