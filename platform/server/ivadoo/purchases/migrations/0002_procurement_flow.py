import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def add_procurement_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    permissions = (
        ("purchase.request.view", "request.view", "View purchase requests"),
        ("purchase.request.manage", "request.manage", "Manage purchase requests"),
        ("purchase.request.approve", "request.approve", "Approve purchase requests"),
        ("purchase.rfq.view", "rfq.view", "View purchase RFQs and quotations"),
        ("purchase.rfq.manage", "rfq.manage", "Manage purchase RFQs and quotations"),
        ("purchase.order.view", "order.view", "View purchase orders"),
        ("purchase.order.manage", "order.manage", "Manage purchase orders"),
        ("purchase.order.approve", "order.approve", "Approve purchase orders"),
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
        ("purchases", "0001_initial"),
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PurchaseRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("rejected", "Rejected"), ("cancelled", "Cancelled")], default="draft", max_length=24)),
                ("needed_by", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("transition_reason", models.CharField(blank=True, max_length=255)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("rejected_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="approved_purchase_requests", to="identity.user")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_requests", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_purchase_requests", to="identity.user")),
                ("establishment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_requests", to="organizations.establishment")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_requests", to="sales.order")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_requests", to="organizations.organization")),
                ("warehouse", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_requests", to="inventory.warehouse")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="PurchaseRequestLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("need_reference_type", models.CharField(blank=True, max_length=80)),
                ("need_reference_id", models.UUIDField(blank=True, null=True)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_request_lines", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_request_lines", to="catalog.productvariant")),
                ("purchase_request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="purchases.purchaserequest")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_request_lines", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.CreateModel(
            name="RequestForQuotation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("sent", "Sent"), ("closed", "Closed"), ("cancelled", "Cancelled")], default="draft", max_length=16)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("transition_reason", models.CharField(blank=True, max_length=255)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_rfqs", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_purchase_rfqs", to="identity.user")),
                ("currency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_rfqs", to="internationalization.currency")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_rfqs", to="organizations.organization")),
                ("purchase_request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="rfqs", to="purchases.purchaserequest")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="RFQSupplier",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("invited_at", models.DateTimeField(auto_now_add=True)),
                ("rfq", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="supplier_links", to="purchases.requestforquotation")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="rfq_links", to="purchases.supplier")),
            ],
        ),
        migrations.CreateModel(
            name="SupplierQuotation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quote_number", models.CharField(blank=True, max_length=96)),
                ("status", models.CharField(choices=[("received", "Received"), ("selected", "Selected"), ("rejected", "Rejected")], default="received", max_length=16)),
                ("quoted_at", models.DateField(blank=True, null=True)),
                ("valid_until", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("rfq", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quotations", to="purchases.requestforquotation")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quotations", to="purchases.supplier")),
            ],
            options={"ordering": ("created_at",)},
        ),
        migrations.CreateModel(
            name="SupplierQuotationLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("unit_price", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("lead_time_days", models.PositiveIntegerField(default=0)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_quotation_lines", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplier_quotation_lines", to="catalog.productvariant")),
                ("quotation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="purchases.supplierquotation")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="supplier_quotation_lines", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.CreateModel(
            name="PurchaseOrder",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("pending_approval", "Pending approval"), ("approved", "Approved"), ("ordered", "Ordered"), ("cancelled", "Cancelled")], default="draft", max_length=24)),
                ("notes", models.TextField(blank=True)),
                ("transition_reason", models.CharField(blank=True, max_length=255)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("ordered_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="approved_purchase_orders", to="identity.user")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_purchase_orders", to="identity.user")),
                ("currency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="internationalization.currency")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="organizations.organization")),
                ("purchase_request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="purchases.purchaserequest")),
                ("quotation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="purchases.supplierquotation")),
                ("rfq", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="purchases.requestforquotation")),
                ("supplier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="purchases.supplier")),
                ("warehouse", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_orders", to="inventory.warehouse")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="PurchaseOrderLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("unit_price", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("expected_date", models.DateField(blank=True, null=True)),
                ("received_quantity", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0"))])),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_order_lines", to="catalog.product")),
                ("product_variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_order_lines", to="catalog.productvariant")),
                ("purchase_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="purchases.purchaseorder")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_order_lines", to="internationalization.unitofmeasure")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.AddConstraint(model_name="purchaserequest", constraint=models.UniqueConstraint(fields=("organization", "number"), name="purchase_request_unique_number_org")),
        migrations.AddConstraint(model_name="requestforquotation", constraint=models.UniqueConstraint(fields=("organization", "number"), name="purchase_rfq_unique_number_org")),
        migrations.AddConstraint(model_name="rfqsupplier", constraint=models.UniqueConstraint(fields=("rfq", "supplier"), name="purchase_rfq_unique_supplier")),
        migrations.AddConstraint(model_name="supplierquotation", constraint=models.UniqueConstraint(fields=("rfq", "supplier"), name="purchase_quote_unique_supplier_rfq")),
        migrations.AddConstraint(model_name="purchaseorder", constraint=models.UniqueConstraint(fields=("organization", "number"), name="purchase_order_unique_number_org")),
        migrations.AddConstraint(model_name="purchaseorderline", constraint=models.CheckConstraint(condition=models.Q(("received_quantity__gte", 0)), name="purchase_order_line_received_nonnegative")),
        migrations.AddConstraint(model_name="purchaseorderline", constraint=models.CheckConstraint(condition=models.Q(("received_quantity__lte", models.F("quantity"))), name="purchase_order_line_received_lte_ordered")),
        migrations.RunPython(add_procurement_permissions, migrations.RunPython.noop),
    ]
