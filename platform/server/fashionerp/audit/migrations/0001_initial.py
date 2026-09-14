import uuid

import django.db.models.deletion
from django.db import migrations, models


IMMUTABILITY_SQL = """
CREATE OR REPLACE FUNCTION fashionerp_reject_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'FashionERP audit events are immutable'
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER fashionerp_audit_event_immutable
BEFORE UPDATE OR DELETE ON audit_auditevent
FOR EACH ROW
EXECUTE FUNCTION fashionerp_reject_audit_mutation();
"""

REVERSE_IMMUTABILITY_SQL = """
DROP TRIGGER IF EXISTS fashionerp_audit_event_immutable ON audit_auditevent;
DROP FUNCTION IF EXISTS fashionerp_reject_audit_mutation();
"""


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("authorization", "0002_add_audit_permission"),
        ("organizations", "0002_company_establishment"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
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
                ("occurred_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("company_id", models.UUIDField(blank=True, db_index=True, null=True)),
                (
                    "establishment_id",
                    models.UUIDField(blank=True, db_index=True, null=True),
                ),
                ("actor_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("actor_login", models.CharField(blank=True, max_length=150)),
                ("action", models.CharField(db_index=True, max_length=160)),
                ("object_type", models.CharField(db_index=True, max_length=160)),
                (
                    "object_id",
                    models.CharField(blank=True, db_index=True, max_length=160),
                ),
                ("object_label", models.CharField(blank=True, max_length=255)),
                (
                    "result",
                    models.CharField(
                        choices=[
                            ("success", "Success"),
                            ("failure", "Failure"),
                            ("denied", "Denied"),
                        ],
                        db_index=True,
                        default="success",
                        max_length=16,
                    ),
                ),
                ("before", models.JSONField(blank=True, null=True)),
                ("after", models.JSONField(blank=True, null=True)),
                ("request_id", models.CharField(blank=True, db_index=True, max_length=128)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "ordering": ("-occurred_at", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["organization", "action", "occurred_at"],
                name="audit_org_action_time_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["organization", "object_type", "object_id"],
                name="audit_org_object_idx",
            ),
        ),
        migrations.RunSQL(
            sql=IMMUTABILITY_SQL,
            reverse_sql=REVERSE_IMMUTABILITY_SQL,
        ),
    ]
