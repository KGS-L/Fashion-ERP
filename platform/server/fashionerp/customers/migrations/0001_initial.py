import uuid

import django.db.models.deletion
import fashionerp.internationalization.validators
from django.db import migrations, models


def add_customer_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    for code, action, name in (
        ("fashion.customer.view", "customer.view", "View customers"),
        ("fashion.customer.manage", "customer.manage", "Manage customers"),
    ):
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "fashion", "action": action, "name": name},
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
            name="Customer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("customer_type", models.CharField(choices=[("individual", "Individual"), ("company", "Company")], default="individual", max_length=16)),
                ("code", models.CharField(max_length=64)),
                ("display_name", models.CharField(max_length=255)),
                ("first_name", models.CharField(blank=True, max_length=120)),
                ("last_name", models.CharField(blank=True, max_length=120)),
                ("legal_name", models.CharField(blank=True, max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=64)),
                ("language_code", models.CharField(choices=[("fr", "Français"), ("en", "English"), ("es", "Español"), ("pt", "Português"), ("ar", "العربية")], default="fr", max_length=8, validators=[fashionerp.internationalization.validators.validate_language_code])),
                ("preferences", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("inactive", "Inactive"), ("archived", "Archived")], default="active", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="customers", to="organizations.company")),
                ("establishment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="customers", to="organizations.establishment")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="customers", to="organizations.organization")),
                ("preferred_currency", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="preferred_by_customers", to="internationalization.currency")),
            ],
            options={"ordering": ("display_name", "code")},
        ),
        migrations.CreateModel(
            name="CustomerAddress",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("address_type", models.CharField(choices=[("billing", "Billing"), ("shipping", "Shipping"), ("home", "Home"), ("work", "Work"), ("other", "Other")], default="other", max_length=16)),
                ("label", models.CharField(blank=True, max_length=80)),
                ("address_line1", models.CharField(max_length=255)),
                ("address_line2", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(blank=True, max_length=120)),
                ("region", models.CharField(blank=True, max_length=120)),
                ("postal_code", models.CharField(blank=True, max_length=32)),
                ("country_code", models.CharField(blank=True, max_length=2)),
                ("is_primary", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="addresses", to="customers.customer")),
            ],
            options={"ordering": ("address_type", "created_at")},
        ),
        migrations.CreateModel(
            name="CustomerConsent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("consent_type", models.CharField(choices=[("marketing", "Marketing"), ("data_processing", "Data processing"), ("photo", "Photo usage"), ("other", "Other")], max_length=32)),
                ("granted", models.BooleanField(default=False)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("note", models.TextField(blank=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="consents", to="customers.customer")),
            ],
            options={"ordering": ("consent_type", "-recorded_at")},
        ),
        migrations.CreateModel(
            name="CustomerContact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("contact_type", models.CharField(choices=[("email", "Email"), ("phone", "Phone"), ("whatsapp", "WhatsApp"), ("other", "Other")], max_length=16)),
                ("label", models.CharField(blank=True, max_length=80)),
                ("value", models.CharField(max_length=255)),
                ("is_primary", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contacts", to="customers.customer")),
            ],
            options={"ordering": ("contact_type", "created_at")},
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(fields=("company", "code"), name="customer_unique_code_per_company"),
        ),
        migrations.RunPython(add_customer_permissions, migrations.RunPython.noop),
    ]
