from django.db import migrations


def add_i18n_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    permissions = (
        (
            "foundation.i18n.view",
            "foundation",
            "i18n.view",
            "View international settings",
        ),
        (
            "foundation.i18n.manage",
            "foundation",
            "i18n.manage",
            "Manage international settings",
        ),
    )
    for code, module, action, name in permissions:
        Permission.objects.update_or_create(
            code=code,
            defaults={
                "module": module,
                "action": action,
                "name": name,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0002_add_audit_permission"),
        ("identity", "0002_user_language_code"),
    ]

    operations = [
        migrations.RunPython(
            add_i18n_permissions,
            migrations.RunPython.noop,
        ),
    ]
