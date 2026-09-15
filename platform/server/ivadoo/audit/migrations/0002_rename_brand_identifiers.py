from django.db import migrations


LEGACY_PREFIX = "fashion" + "erp"
CURRENT_PREFIX = "ivadoo"


def _rename_audit_identifiers(schema_editor, source_prefix: str, target_prefix: str) -> None:
    source_trigger = f"{source_prefix}_audit_event_immutable"
    target_trigger = f"{target_prefix}_audit_event_immutable"
    source_function = f"{source_prefix}_reject_audit_mutation"
    target_function = f"{target_prefix}_reject_audit_mutation"

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS ("
            "SELECT 1 FROM pg_trigger "
            "WHERE tgname = %s AND tgrelid = 'audit_auditevent'::regclass"
            ")",
            [source_trigger],
        )
        if cursor.fetchone()[0]:
            schema_editor.execute(
                f'ALTER TRIGGER "{source_trigger}" ON audit_auditevent '
                f'RENAME TO "{target_trigger}"'
            )

        cursor.execute("SELECT to_regprocedure(%s)", [f"{source_function}()"])
        if cursor.fetchone()[0] is not None:
            schema_editor.execute(
                f'ALTER FUNCTION "{source_function}"() RENAME TO "{target_function}"'
            )


def forwards(apps, schema_editor):
    _rename_audit_identifiers(schema_editor, LEGACY_PREFIX, CURRENT_PREFIX)


def backwards(apps, schema_editor):
    _rename_audit_identifiers(schema_editor, CURRENT_PREFIX, LEGACY_PREFIX)


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
