import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_foundation_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    definitions = (
        ("foundation.organization.view", "foundation", "organization.view", "View organization"),
        ("foundation.company.view", "foundation", "company.view", "View companies"),
        ("foundation.company.manage", "foundation", "company.manage", "Manage companies"),
        ("foundation.establishment.view", "foundation", "establishment.view", "View establishments"),
        ("foundation.establishment.manage", "foundation", "establishment.manage", "Manage establishments"),
        ("foundation.access.manage", "foundation", "access.manage", "Manage access"),
    )
    for code, module, action, name in definitions:
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": module, "action": action, "name": name},
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0002_company_establishment"),
    ]

    operations = [
        migrations.CreateModel(
            name="Permission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=160, unique=True)),
                ("module", models.CharField(max_length=80)),
                ("action", models.CharField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
            ],
            options={"ordering": ("code",)},
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("is_full_access", models.BooleanField(default=False)),
                ("is_system", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="access_roles", to="organizations.organization")),
                ("permissions", models.ManyToManyField(blank=True, related_name="roles", to="authorization.permission")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.UniqueConstraint(fields=("organization", "code"), name="role_unique_code_per_organization"),
        ),
        migrations.CreateModel(
            name="AccessGroup",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="access_groups", to="organizations.organization")),
                ("members", models.ManyToManyField(blank=True, related_name="access_groups", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.AddConstraint(
            model_name="accessgroup",
            constraint=models.UniqueConstraint(fields=("organization", "code"), name="access_group_unique_code_per_organization"),
        ),
        migrations.CreateModel(
            name="AccessGrant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="access_grants", to="organizations.company")),
                ("establishment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="access_grants", to="organizations.establishment")),
                ("group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="access_grants", to="authorization.accessgroup")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="grants", to="authorization.role")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="access_grants", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="accessgrant",
            constraint=models.CheckConstraint(
                condition=models.Q(("group__isnull", True), ("user__isnull", False), _connector="OR") & ~models.Q(("group__isnull", False), ("user__isnull", False)),
                name="access_grant_exactly_one_principal",
            ),
        ),
        migrations.AddConstraint(
            model_name="accessgrant",
            constraint=models.CheckConstraint(
                condition=~models.Q(("company__isnull", False), ("establishment__isnull", False)),
                name="access_grant_single_scope_target",
            ),
        ),
        migrations.RunPython(seed_foundation_permissions, migrations.RunPython.noop),
    ]
