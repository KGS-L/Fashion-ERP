import uuid

import django.db.models.deletion
from django.db import migrations, models


def add_product_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    for code, action, name in (
        ("fashion.product.view", "product.view", "View products"),
        ("fashion.product.manage", "product.manage", "Manage products"),
    ):
        Permission.objects.update_or_create(
            code=code, defaults={"module": "fashion", "action": action, "name": name}
        )


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("authorization", "0003_add_i18n_permissions"),
        ("internationalization", "0001_initial"),
        ("organizations", "0003_international_settings"),
    ]
    operations = [
        migrations.CreateModel(
            name="ProductAttribute",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("is_active", models.BooleanField(default=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="product_attributes", to="organizations.organization")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("product_type", models.CharField(choices=[("finished_good","Finished good"),("fabric","Fabric"),("accessory","Accessory"),("service","Service"),("packaging","Packaging"),("waste","Waste")], max_length=24)),
                ("fashion_metadata", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="products", to="organizations.company")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="products", to="organizations.organization")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="products", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="ProductAttributeValue",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80)),
                ("value", models.CharField(max_length=160)),
                ("position", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("attribute", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="values", to="catalog.productattribute")),
            ],
            options={"ordering": ("position", "value")},
        ),
        migrations.CreateModel(
            name="ProductVariant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sku", models.CharField(max_length=96)),
                ("barcode", models.CharField(blank=True, max_length=128)),
                ("name", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="variants", to="catalog.product")),
            ],
            options={"ordering": ("sku",)},
        ),
        migrations.CreateModel(
            name="ProductVariantAttributeValue",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("attribute_value", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="variant_attribute_values", to="catalog.productattributevalue")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="variant_attribute_values", to="catalog.productvariant")),
            ],
        ),
        migrations.AddField(model_name="productvariant", name="attribute_values", field=models.ManyToManyField(related_name="variants", through="catalog.ProductVariantAttributeValue", to="catalog.productattributevalue")),
        migrations.AddConstraint(model_name="productattribute", constraint=models.UniqueConstraint(fields=("organization","code"), name="product_attribute_unique_code_per_org")),
        migrations.AddConstraint(model_name="product", constraint=models.UniqueConstraint(fields=("organization","code"), name="product_unique_code_per_org")),
        migrations.AddConstraint(model_name="productattributevalue", constraint=models.UniqueConstraint(fields=("attribute","code"), name="product_attribute_value_unique_code")),
        migrations.AddConstraint(model_name="productvariant", constraint=models.UniqueConstraint(fields=("product","sku"), name="product_variant_unique_sku_per_product")),
        migrations.AddConstraint(model_name="productvariant", constraint=models.UniqueConstraint(condition=~models.Q(("barcode","")), fields=("product","barcode"), name="product_variant_unique_barcode_per_product")),
        migrations.AddConstraint(model_name="productvariantattributevalue", constraint=models.UniqueConstraint(fields=("variant","attribute_value"), name="variant_unique_attribute_value")),
        migrations.RunPython(add_product_permissions, migrations.RunPython.noop),
    ]
