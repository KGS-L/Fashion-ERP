import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def add_receipt_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    permissions = (
        ("purchase.receipt.view", "receipt.view", "View purchase receipts"),
        ("purchase.receipt.manage", "receipt.manage", "Manage purchase receipts"),
        ("purchase.receipt.control", "receipt.control", "Control purchase receipt quality"),
        ("purchase.receipt.post", "receipt.post", "Post accepted purchase receipts to stock"),
    )
    for code, action, name in permissions:
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "purchase", "action": action, "name": name},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0004_two_factor_security"),
        ("inventory", "0001_initial"),
        ("purchases", "0002_procurement_flow"),
    ]

    operations = [
        migrations.CreateModel(
            name="PurchaseReceipt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.CharField(max_length=64)),
                ("supplier_delivery_reference", models.CharField(blank=True, max_length=128)),
                ("received_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("controlled", "Controlled"), ("posted", "Posted"), ("cancelled", "Cancelled")], default="draft", max_length=16)),
                ("notes", models.TextField(blank=True)),
                ("transition_reason", models.CharField(blank=True, max_length=255)),
                ("controlled_at", models.DateTimeField(blank=True, null=True)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_receipts", to="organizations.company")),
                ("controlled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="controlled_purchase_receipts", to="identity.user")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_purchase_receipts", to="identity.user")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_receipts", to="organizations.organization")),
                ("posted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="posted_purchase_receipts", to="identity.user")),
                ("purchase_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipts", to="purchases.purchaseorder")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_receipts", to="inventory.warehouse")),
            ],
            options={"ordering": ("-received_at", "-created_at")},
        ),
        migrations.CreateModel(
            name="PurchaseReceiptLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("received_quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("accepted_quantity", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("rejected_quantity", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("quality_status", models.CharField(choices=[("pending", "Pending control"), ("accepted", "Accepted"), ("partial", "Partially accepted"), ("rejected", "Rejected")], default="pending", max_length=16)),
                ("control_note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_receipt_lines", to="inventory.stocklocation")),
                ("purchase_order_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="receipt_lines", to="purchases.purchaseorderline")),
                ("receipt", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="purchases.purchasereceipt")),
                ("stock_movement", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_receipt_lines", to="inventory.stockmovement")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.CreateModel(
            name="SupplierPurchaseHistory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("unit_price", models.DecimalField(decimal_places=4, max_digits=18)),
                ("ordered_quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("received_quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("accepted_quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("rejected_quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("expected_date", models.DateField(blank=True, null=True)),
                ("received_at", models.DateTimeField()),
                ("ordered_at", models.DateTimeField(blank=True, null=True)),
                ("lead_time_days", models.PositiveIntegerField(default=0)),
                ("on_time", models.BooleanField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_purchase_history", to="organizations.company")),
                ("currency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_purchase_history", to="internationalization.currency")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_purchase_history", to="organizations.organization")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_purchase_history", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplier_purchase_history", to="catalog.productvariant")),
                ("receipt_line", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_history", to="purchases.purchasereceiptline")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_history", to="purchases.supplier")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_purchase_history", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("-received_at", "-created_at")},
        ),
        migrations.AddConstraint(
            model_name="purchasereceipt",
            constraint=models.UniqueConstraint(fields=("organization", "number"), name="purchase_receipt_unique_number_org"),
        ),
        migrations.AddConstraint(
            model_name="purchasereceiptline",
            constraint=models.UniqueConstraint(fields=("receipt", "purchase_order_line"), name="purchase_receipt_unique_order_line"),
        ),
        migrations.AddConstraint(
            model_name="purchasereceiptline",
            constraint=models.CheckConstraint(condition=models.Q(("received_quantity__gt", 0)), name="purchase_receipt_line_received_positive"),
        ),
        migrations.AddConstraint(
            model_name="purchasereceiptline",
            constraint=models.CheckConstraint(condition=models.Q(("accepted_quantity__gte", 0)), name="purchase_receipt_line_accepted_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="purchasereceiptline",
            constraint=models.CheckConstraint(condition=models.Q(("rejected_quantity__gte", 0)), name="purchase_receipt_line_rejected_nonnegative"),
        ),
        migrations.AddIndex(
            model_name="supplierpurchasehistory",
            index=models.Index(fields=["organization", "supplier", "received_at"], name="purchase_supplier_history_idx"),
        ),
        migrations.RunPython(add_receipt_permissions, migrations.RunPython.noop),
    ]
