import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0003_user_language_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="apisession",
            name="ip_address",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="apisession",
            name="two_factor_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="TotpCredential",
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
                ("encrypted_secret", models.TextField(editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="totp_credential",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("user_id",)},
        ),
        migrations.CreateModel(
            name="RecoveryCode",
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
                ("code_digest", models.CharField(editable=False, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recovery_codes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("created_at",)},
        ),
        migrations.AddConstraint(
            model_name="recoverycode",
            constraint=models.UniqueConstraint(
                fields=("user", "code_digest"),
                name="identity_unique_recovery_code_digest_per_user",
            ),
        ),
    ]
