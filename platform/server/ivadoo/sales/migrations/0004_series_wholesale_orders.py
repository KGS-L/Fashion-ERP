import uuid

import django.db.models.deletion
from django.db import migrations, models


def add_sales_approval_permission(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Permission.objects.update_or_create(
        code="fashion.sale.approve",
        defaults={
            "module": "fashion",
            "action": "sale.approve",
            "name": "Approve controlled fashion sales",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0003_add_i18n_permissions"),
        ("catalog", "0004_internal_catalog"),
        ("identity", "0004_two_factor_security"),
        ("operations", "0002_sales_order_approval_resource"),
        ("sales", "0003_sales_line_value_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_fashion_orders",
                to="identity.user",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="order_type",
            field=models.CharField(
                choices=[
                    ("custom", "Custom"),
                    ("series", "Series"),
                    ("wholesale", "Wholesale"),
                ],
                default="custom",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="orderline",
            name="commercial_customization",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="orderline",
            name="discount_rate",
            field=models.DecimalField(decimal_places=4, default=0, max_digits=7),
        ),
        migrations.AddField(
            model_name="orderline",
            name="fulfillment_mode",
            field=models.CharField(
                choices=[
                    ("auto", "Automatic"),
                    ("finished_stock", "Finished stock"),
                    ("production", "Production"),
                ],
                default="auto",
                max_length=24,
            ),
        ),
        migrations.AddConstraint(
            model_name="orderline",
            constraint=models.CheckConstraint(
                condition=models.Q(discount_rate__gte=0)
                & models.Q(discount_rate__lte=1),
                name="order_line_discount_rate_range",
            ),
        ),
        migrations.CreateModel(
            name="OrderLineVariantQuantity",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=14)),
                ("commercial_customization", models.JSONField(blank=True, default=dict)),
                (
                    "model_variant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="order_line_quantities",
                        to="catalog.fashionmodelvariant",
                    ),
                ),
                (
                    "order_line",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variant_quantities",
                        to="sales.orderline",
                    ),
                ),
            ],
            options={"ordering": ("model_variant__code",)},
        ),
        migrations.AddConstraint(
            model_name="orderlinevariantquantity",
            constraint=models.UniqueConstraint(
                fields=("order_line", "model_variant"),
                name="order_line_variant_quantity_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderlinevariantquantity",
            constraint=models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_line_variant_quantity_positive",
            ),
        ),
        migrations.CreateModel(
            name="OrderCommercialSnapshot",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "order_type",
                    models.CharField(
                        choices=[
                            ("custom", "Custom"),
                            ("series", "Series"),
                            ("wholesale", "Wholesale"),
                        ],
                        max_length=16,
                    ),
                ),
                ("subtotal", models.DecimalField(decimal_places=4, max_digits=18)),
                ("discount_total", models.DecimalField(decimal_places=4, max_digits=18)),
                ("total", models.DecimalField(decimal_places=4, max_digits=18)),
                ("payload", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "confirmed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="confirmed_order_commercial_snapshots",
                        to="identity.user",
                    ),
                ),
                (
                    "order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="commercial_snapshot",
                        to="sales.order",
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="ordercommercialsnapshot",
            constraint=models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="order_commercial_snapshot_subtotal_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="ordercommercialsnapshot",
            constraint=models.CheckConstraint(
                condition=models.Q(discount_total__gte=0),
                name="order_commercial_snapshot_discount_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="ordercommercialsnapshot",
            constraint=models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name="order_commercial_snapshot_total_nonnegative",
            ),
        ),
        migrations.RunPython(add_sales_approval_permission, migrations.RunPython.noop),
    ]
