import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_fashion_collections_models"),
        ("internationalization", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="FashionModelMaterialRequirement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=14)),
                ("waste_rate", models.DecimalField(decimal_places=4, default=0, max_digits=7)),
                ("notes", models.TextField(blank=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("fashion_model", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="material_requirements", to="catalog.fashionmodel")),
                ("model_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="material_requirements", to="catalog.fashionmodelvariant")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fashion_model_requirements", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="fashion_model_requirements", to="catalog.productvariant")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fashion_model_requirements", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("position", "product__name")},
        ),
        migrations.AddConstraint(model_name="fashionmodelmaterialrequirement", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="fashion_requirement_positive_quantity")),
        migrations.AddConstraint(model_name="fashionmodelmaterialrequirement", constraint=models.CheckConstraint(condition=models.Q(("waste_rate__gte", 0)), name="fashion_requirement_nonnegative_waste")),
        migrations.AddConstraint(model_name="fashionmodelmaterialrequirement", constraint=models.UniqueConstraint(fields=("fashion_model","model_variant","product","product_variant"), name="fashion_requirement_unique_material")),
    ]
