import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def add_delivery_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    permissions = (
        ("delivery.delivery.view", "delivery.view", "View deliveries"),
        ("delivery.delivery.manage", "delivery.manage", "Create and manage delivery preparation"),
        ("delivery.delivery.transition", "delivery.transition", "Transition deliveries and record proof"),
    )
    for code, action, name in permissions:
        Permission.objects.update_or_create(code=code, defaults={"module": "delivery", "action": action, "name": name})


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("authorization", "0003_add_i18n_permissions"),
        ("sales", "0002_fittings_alterations_customer_validation"),
        ("manufacturing", "0003_material_flow_and_output"),
        ("quality", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Delivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("number", models.CharField(max_length=64)),
                ("mode", models.CharField(choices=[("pickup", "Pickup"), ("local_delivery", "Local delivery")], max_length=24)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("prepared", "Prepared"), ("assigned", "Assigned"), ("shipped", "Shipped"), ("ready_for_pickup", "Ready for pickup"), ("picked_up", "Picked up"), ("delivered", "Delivered"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="draft", max_length=24)),
                ("courier_name", models.CharField(blank=True, max_length=160)),
                ("courier_reference", models.CharField(blank=True, max_length=160)),
                ("destination_notes", models.TextField(blank=True)),
                ("failure_reason", models.CharField(blank=True, max_length=255)),
                ("prepared_at", models.DateTimeField(blank=True, null=True)),
                ("assigned_at", models.DateTimeField(blank=True, null=True)),
                ("shipped_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deliveries", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_deliveries", to="identity.user")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deliveries", to="sales.order")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deliveries", to="organizations.organization")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="DeliveryLine",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("delivery", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="delivery.delivery")),
                ("order_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="delivery_lines", to="sales.orderline")),
            ],
            options={"ordering": ("order_line_id",)},
        ),
        migrations.CreateModel(
            name="DeliveryPackage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=80)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("is_sealed", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("delivery", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="packages", to="delivery.delivery")),
            ],
            options={"ordering": ("code",)},
        ),
        migrations.CreateModel(
            name="DeliveryProof",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("proof_type", models.CharField(choices=[("recipient_ack", "Recipient acknowledgement"), ("signature", "Signature"), ("photo", "Photo"), ("code", "Code")], max_length=24)),
                ("recipient_name", models.CharField(max_length=160)),
                ("evidence_reference", models.CharField(blank=True, max_length=500)),
                ("notes", models.TextField(blank=True)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("delivery", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="proof", to="delivery.delivery")),
                ("recorded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="recorded_delivery_proofs", to="identity.user")),
            ],
            options={"ordering": ("-recorded_at",)},
        ),
        migrations.AddConstraint(model_name="delivery", constraint=models.UniqueConstraint(fields=("organization", "number"), name="delivery_unique_number_org")),
        migrations.AddConstraint(model_name="deliveryline", constraint=models.UniqueConstraint(fields=("delivery", "order_line"), name="delivery_unique_order_line")),
        migrations.AddConstraint(model_name="deliveryline", constraint=models.CheckConstraint(condition=models.Q(quantity__gt=0), name="delivery_line_quantity_positive")),
        migrations.AddConstraint(model_name="deliverypackage", constraint=models.UniqueConstraint(fields=("delivery", "code"), name="delivery_package_unique_code")),
        migrations.RunPython(add_delivery_permissions, migrations.RunPython.noop),
    ]
