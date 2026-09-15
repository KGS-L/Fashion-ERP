import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import ivadoo.internationalization.validators


def add_purchase_supplier_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    for code, action, name in (
        ("purchase.supplier.view", "supplier.view", "View suppliers"),
        ("purchase.supplier.manage", "supplier.manage", "Manage suppliers"),
    ):
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "purchase", "action": action, "name": name},
        )


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("authorization", "0003_add_i18n_permissions"),
        ("catalog", "0004_internal_catalog"),
        ("internationalization", "0001_initial"),
        ("organizations", "0003_international_settings"),
    ]
    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("legal_name", models.CharField(blank=True, max_length=255)),
                ("tax_identifier", models.CharField(blank=True, max_length=128)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=64)),
                ("website", models.URLField(blank=True)),
                ("language_code", models.CharField(choices=[("fr", "Français"), ("en", "English"), ("es", "Español"), ("pt", "Português"), ("ar", "العربية")], default="fr", max_length=8, validators=[ivadoo.internationalization.validators.validate_language_code])),
                ("lead_time_days", models.PositiveIntegerField(default=0)),
                ("minimum_order_amount", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("notes", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("blocked", "Blocked"), ("archived", "Archived")], default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="suppliers", to="organizations.company")),
                ("currency", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_suppliers", to="internationalization.currency")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="suppliers", to="organizations.organization")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="SupplierAddress",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("label", models.CharField(blank=True, max_length=120)),
                ("address_line1", models.CharField(max_length=255)),
                ("address_line2", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(max_length=120)),
                ("region", models.CharField(blank=True, max_length=120)),
                ("postal_code", models.CharField(blank=True, max_length=32)),
                ("country_code", models.CharField(blank=True, max_length=2)),
                ("is_primary", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="addresses", to="purchases.supplier")),
            ],
            options={"ordering": ("-is_primary", "label", "city")},
        ),
        migrations.CreateModel(
            name="SupplierContact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("role", models.CharField(blank=True, max_length=120)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=64)),
                ("is_primary", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contacts", to="purchases.supplier")),
            ],
            options={"ordering": ("-is_primary", "name")},
        ),
        migrations.CreateModel(
            name="SupplierProduct",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("supplier_sku", models.CharField(blank=True, max_length=96)),
                ("lead_time_days", models.PositiveIntegerField(blank=True, null=True)),
                ("minimum_quantity", models.DecimalField(decimal_places=4, default=Decimal("1"), max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("last_unit_price", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("is_preferred", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("currency", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplier_products", to="internationalization.currency")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_links", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplier_links", to="catalog.productvariant")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="products", to="purchases.supplier")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_products", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("supplier__name", "product__name")},
        ),
        migrations.AddConstraint(model_name="supplier", constraint=models.UniqueConstraint(fields=("organization", "code"), name="purchase_supplier_unique_code_org")),
        migrations.AddConstraint(model_name="supplierproduct", constraint=models.UniqueConstraint(condition=models.Q(("product_variant__isnull", True)), fields=("supplier", "product"), name="purchase_supplier_product_unique_base")),
        migrations.AddConstraint(model_name="supplierproduct", constraint=models.UniqueConstraint(condition=models.Q(("product_variant__isnull", False)), fields=("supplier", "product_variant"), name="purchase_supplier_product_unique_variant")),
        migrations.RunPython(add_purchase_supplier_permissions, migrations.RunPython.noop),
    ]
