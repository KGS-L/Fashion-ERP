import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def add_manufacturing_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    permissions = (
        ("manufacturing.bom.view", "bom.view", "View operational bills of materials"),
        ("manufacturing.bom.manage", "bom.manage", "Manage operational bills of materials"),
        ("manufacturing.order.view", "order.view", "View manufacturing orders"),
        ("manufacturing.order.manage", "order.manage", "Manage manufacturing orders"),
        ("manufacturing.order.transition", "order.transition", "Transition manufacturing orders"),
        ("manufacturing.material.reserve", "material.reserve", "Reserve manufacturing materials"),
    )
    for code, action, name in permissions:
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "manufacturing", "action": action, "name": name},
        )


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("authorization", "0003_add_i18n_permissions"),
        ("catalog", "0004_internal_catalog"),
        ("identity", "0004_two_factor_security"),
        ("inventory", "0001_initial"),
        ("organizations", "0003_international_settings"),
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BillOfMaterials",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=80)),
                ("version", models.PositiveIntegerField(default=1)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("active", "Active"), ("archived", "Archived")], default="draft", max_length=16)),
                ("batch_quantity", models.DecimalField(decimal_places=4, default=Decimal("1"), max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("notes", models.TextField(blank=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_boms", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_manufacturing_boms", to="identity.user")),
                ("fashion_model", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operational_boms", to="catalog.fashionmodel")),
                ("model_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="operational_boms", to="catalog.fashionmodelvariant")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_boms", to="organizations.organization")),
                ("output_product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_output_boms", to="catalog.product")),
                ("output_product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_output_boms", to="catalog.productvariant")),
            ],
            options={"ordering": ("code", "-version")},
        ),
        migrations.CreateModel(
            name="BillOfMaterialsLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("waste_rate", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=7, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("notes", models.TextField(blank=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("bom", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="manufacturing.billofmaterials")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_bom_lines", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_bom_lines", to="catalog.productvariant")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_bom_lines", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("position", "id")},
        ),
        migrations.CreateModel(
            name="ManufacturingOrder",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("ready", "Ready"), ("in_progress", "In progress"), ("done", "Done"), ("cancelled", "Cancelled")], default="draft", max_length=16)),
                ("planned_quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("produced_quantity", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("planned_start", models.DateTimeField(blank=True, null=True)),
                ("planned_end", models.DateTimeField(blank=True, null=True)),
                ("actual_start", models.DateTimeField(blank=True, null=True)),
                ("actual_end", models.DateTimeField(blank=True, null=True)),
                ("transition_reason", models.CharField(blank=True, max_length=255)),
                ("bom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_orders", to="manufacturing.billofmaterials")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_orders", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_manufacturing_orders", to="identity.user")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_orders", to="sales.order")),
                ("order_line", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_orders", to="sales.orderline")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_orders", to="organizations.organization")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_orders", to="inventory.warehouse")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="ManufacturingMaterialRequirement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity_per_unit", models.DecimalField(decimal_places=4, max_digits=18)),
                ("waste_rate", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=7)),
                ("planned_quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("manufacturing_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="material_requirements", to="manufacturing.manufacturingorder")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_requirements", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_requirements", to="catalog.productvariant")),
                ("source_bom_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_requirement_snapshots", to="manufacturing.billofmaterialsline")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_requirements", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("source_bom_line__position", "id")},
        ),
        migrations.AddConstraint(
            model_name="billofmaterials",
            constraint=models.UniqueConstraint(fields=("organization", "code", "version"), name="manufacturing_bom_unique_version_org"),
        ),
        migrations.AddConstraint(
            model_name="billofmaterials",
            constraint=models.CheckConstraint(condition=models.Q(("batch_quantity__gt", 0)), name="manufacturing_bom_batch_positive"),
        ),
        migrations.AddConstraint(
            model_name="billofmaterialsline",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="manufacturing_bom_line_quantity_positive"),
        ),
        migrations.AddConstraint(
            model_name="billofmaterialsline",
            constraint=models.CheckConstraint(condition=models.Q(("waste_rate__gte", 0)), name="manufacturing_bom_line_waste_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingorder",
            constraint=models.UniqueConstraint(fields=("organization", "number"), name="manufacturing_order_unique_number_org"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingorder",
            constraint=models.CheckConstraint(condition=models.Q(("planned_quantity__gt", 0)), name="manufacturing_order_planned_positive"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingorder",
            constraint=models.CheckConstraint(condition=models.Q(("produced_quantity__gte", 0)), name="manufacturing_order_produced_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingorder",
            constraint=models.CheckConstraint(condition=models.Q(("produced_quantity__lte", models.F("planned_quantity"))), name="manufacturing_order_produced_lte_planned"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingmaterialrequirement",
            constraint=models.UniqueConstraint(fields=("manufacturing_order", "source_bom_line"), name="manufacturing_requirement_unique_bom_line"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingmaterialrequirement",
            constraint=models.CheckConstraint(condition=models.Q(("quantity_per_unit__gt", 0)), name="manufacturing_requirement_per_unit_positive"),
        ),
        migrations.AddConstraint(
            model_name="manufacturingmaterialrequirement",
            constraint=models.CheckConstraint(condition=models.Q(("planned_quantity__gt", 0)), name="manufacturing_requirement_planned_positive"),
        ),
        migrations.RunPython(add_manufacturing_permissions, migrations.RunPython.noop),
    ]
