from django.db import migrations


def add_audit_permission(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    Permission.objects.update_or_create(
        code="foundation.audit.view",
        defaults={
            "module": "foundation",
            "action": "audit.view",
            "name": "View audit journal",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(add_audit_permission, migrations.RunPython.noop),
    ]
