import uuid

import django.db.models.deletion
from django.db import migrations, models


def add_inventory_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    for code, action, name in (
        ("inventory.stock.view", "stock.view", "View inventory"),
        ("inventory.stock.manage", "stock.manage", "Manage inventory"),
        ("inventory.stock.reserve", "stock.reserve", "Reserve inventory"),
    ):
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "inventory", "action": action, "name": name},
        )


IMMUTABILITY_SQL = """
CREATE OR REPLACE FUNCTION ivadoo_reject_stock_movement_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Ivadoo stock movements are immutable'
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER ivadoo_stock_movement_immutable
BEFORE UPDATE OR DELETE ON inventory_stockmovement
FOR EACH ROW
EXECUTE FUNCTION ivadoo_reject_stock_movement_mutation();
"""

REVERSE_IMMUTABILITY_SQL = """
DROP TRIGGER IF EXISTS ivadoo_stock_movement_immutable ON inventory_stockmovement;
DROP FUNCTION IF EXISTS ivadoo_reject_stock_movement_mutation();
"""


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("authorization", "0003_add_i18n_permissions"),
        ("catalog", "0004_internal_catalog"),
        ("identity", "0004_two_factor_security"),
        ("internationalization", "0001_initial"),
        ("organizations", "0003_international_settings"),
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouses", to="organizations.company")),
                ("establishment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="warehouses", to="organizations.establishment")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warehouses", to="organizations.organization")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="StockLocation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=255)),
                ("kind", models.CharField(choices=[("internal", "Internal"), ("receiving", "Receiving"), ("shipping", "Shipping"), ("production", "Production"), ("damaged", "Damaged"), ("subcontractor", "Subcontractor")], default="internal", max_length=24)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="inventory.stocklocation")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="locations", to="inventory.warehouse")),
            ],
            options={"ordering": ("warehouse__name", "code")},
        ),
        migrations.CreateModel(
            name="StockLot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=96)),
                ("kind", models.CharField(choices=[("lot", "Lot"), ("roll", "Roll"), ("remnant", "Reusable remnant")], default="lot", max_length=16)),
                ("origin", models.CharField(blank=True, max_length=255)),
                ("supplier_reference", models.CharField(blank=True, max_length=160)),
                ("width", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("initial_length", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("remaining_length", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("initial_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("remaining_quantity", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("reusable", models.BooleanField(default=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("exhausted", "Exhausted"), ("blocked", "Blocked")], default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lots", to="inventory.stocklocation")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_lots", to="organizations.organization")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_lots", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_lots", to="catalog.productvariant")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_lots", to="internationalization.unitofmeasure")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lots", to="inventory.warehouse")),
            ],
            options={"ordering": ("code",)},
        ),
        migrations.CreateModel(
            name="StockPosition",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity_available", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("quantity_reserved", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("quantity_in_production", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("quantity_damaged", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("quantity_subcontractor", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="positions", to="inventory.stocklocation")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_positions", to="organizations.organization")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_positions", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_positions", to="catalog.productvariant")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_positions", to="internationalization.unitofmeasure")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="positions", to="inventory.warehouse")),
            ],
            options={"ordering": ("warehouse__name", "location__code", "product__name")},
        ),
        migrations.CreateModel(
            name="StockReservation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("production_order_id", models.UUIDField(blank=True, null=True)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("status", models.CharField(choices=[("active", "Active"), ("in_production", "In production"), ("released", "Released"), ("consumed", "Consumed")], default="active", max_length=24)),
                ("idempotency_key", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_reservations", to="organizations.company")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="created_stock_reservations", to="identity.user")),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="inventory.stocklocation")),
                ("lot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="inventory.stocklot")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_reservations", to="sales.order")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_reservations", to="organizations.organization")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_reservations", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_reservations", to="catalog.productvariant")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_reservations", to="internationalization.unitofmeasure")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="inventory.warehouse")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("movement_type", models.CharField(choices=[("receipt", "Receipt"), ("issue", "Issue"), ("transfer", "Transfer"), ("adjustment_in", "Adjustment in"), ("adjustment_out", "Adjustment out"), ("return_in", "Return in"), ("production_output", "Production output"), ("damage", "Mark damaged"), ("restore_damage", "Restore damaged"), ("production_consumption", "Production consumption")], max_length=32)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("reference_type", models.CharField(blank=True, max_length=80)),
                ("reference_id", models.UUIDField(blank=True, null=True)),
                ("idempotency_key", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="organizations.company")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="created_stock_movements", to="identity.user")),
                ("destination_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="incoming_movements", to="inventory.stocklocation")),
                ("lot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="inventory.stocklot")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="organizations.organization")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="catalog.productvariant")),
                ("source_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_movements", to="inventory.stocklocation")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddConstraint(model_name="warehouse", constraint=models.UniqueConstraint(fields=("organization", "code"), name="inventory_warehouse_unique_code_org")),
        migrations.AddConstraint(model_name="stocklocation", constraint=models.UniqueConstraint(fields=("warehouse", "code"), name="inventory_location_unique_code_warehouse")),
        migrations.AddConstraint(model_name="stocklot", constraint=models.UniqueConstraint(fields=("organization", "code"), name="inventory_lot_unique_code_org")),
        migrations.AddConstraint(model_name="stocklot", constraint=models.CheckConstraint(condition=models.Q(("initial_quantity__gte", 0)), name="inventory_lot_initial_quantity_nonnegative")),
        migrations.AddConstraint(model_name="stocklot", constraint=models.CheckConstraint(condition=models.Q(("remaining_quantity__gte", 0)), name="inventory_lot_remaining_quantity_nonnegative")),
        migrations.AddConstraint(model_name="stocklot", constraint=models.CheckConstraint(condition=models.Q(("initial_length__isnull", True), ("initial_length__gte", 0), _connector="OR"), name="inventory_lot_initial_length_nonnegative")),
        migrations.AddConstraint(model_name="stocklot", constraint=models.CheckConstraint(condition=models.Q(("remaining_length__isnull", True), ("remaining_length__gte", 0), _connector="OR"), name="inventory_lot_remaining_length_nonnegative")),
        migrations.AddConstraint(model_name="stockposition", constraint=models.UniqueConstraint(fields=("organization", "location", "product", "product_variant", "unit"), name="inventory_position_unique_scope", nulls_distinct=False)),
        migrations.AddConstraint(model_name="stockposition", constraint=models.CheckConstraint(condition=models.Q(("quantity_available__gte", 0)), name="inventory_position_available_nonnegative")),
        migrations.AddConstraint(model_name="stockposition", constraint=models.CheckConstraint(condition=models.Q(("quantity_reserved__gte", 0)), name="inventory_position_reserved_nonnegative")),
        migrations.AddConstraint(model_name="stockposition", constraint=models.CheckConstraint(condition=models.Q(("quantity_in_production__gte", 0)), name="inventory_position_production_nonnegative")),
        migrations.AddConstraint(model_name="stockposition", constraint=models.CheckConstraint(condition=models.Q(("quantity_damaged__gte", 0)), name="inventory_position_damaged_nonnegative")),
        migrations.AddConstraint(model_name="stockposition", constraint=models.CheckConstraint(condition=models.Q(("quantity_subcontractor__gte", 0)), name="inventory_position_subcontractor_nonnegative")),
        migrations.AddConstraint(model_name="stockreservation", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="inventory_reservation_positive_quantity")),
        migrations.AddConstraint(model_name="stockreservation", constraint=models.UniqueConstraint(condition=~models.Q(("idempotency_key", "")), fields=("organization", "idempotency_key"), name="inventory_reservation_unique_idempotency_org")),
        migrations.AddConstraint(model_name="stockmovement", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="inventory_movement_positive_quantity")),
        migrations.AddConstraint(model_name="stockmovement", constraint=models.UniqueConstraint(condition=~models.Q(("idempotency_key", "")), fields=("organization", "idempotency_key"), name="inventory_movement_unique_idempotency_org")),
        migrations.RunPython(add_inventory_permissions, migrations.RunPython.noop),
        migrations.RunSQL(sql=IMMUTABILITY_SQL, reverse_sql=REVERSE_IMMUTABILITY_SQL),
    ]
