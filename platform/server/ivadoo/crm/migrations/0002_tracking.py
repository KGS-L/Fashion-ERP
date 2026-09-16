import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("crm", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CRMSegment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_segments", to="organizations.company")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_segments", to="organizations.organization")),
            ],
            options={"ordering": ("company__name", "name", "code")},
        ),
        migrations.CreateModel(
            name="CRMSegmentMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("added_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="added_crm_segment_memberships", to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_segment_memberships", to="organizations.company")),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="crm_segment_memberships", to="customers.customer")),
                ("lead", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="segment_memberships", to="crm.crmlead")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_segment_memberships", to="organizations.organization")),
                ("segment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="crm.crmsegment")),
            ],
            options={"ordering": ("segment__name", "-added_at", "-id")},
        ),
        migrations.CreateModel(
            name="CRMFollowUp",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("subject", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("due_at", models.DateTimeField()),
                ("status", models.CharField(choices=[("planned", "Planned"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="planned", max_length=16)),
                ("priority", models.CharField(choices=[("low", "Low"), ("normal", "Normal"), ("high", "High")], default="normal", max_length=16)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assignee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="assigned_crm_followups", to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_followups", to="organizations.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_crm_followups", to=settings.AUTH_USER_MODEL)),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="crm_followups", to="customers.customer")),
                ("establishment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="crm_followups", to="organizations.establishment")),
                ("lead", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="followups", to="crm.crmlead")),
                ("opportunity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="followups", to="crm.crmopportunity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_followups", to="organizations.organization")),
            ],
            options={"ordering": ("status", "due_at", "-created_at")},
        ),
        migrations.CreateModel(
            name="CRMInteraction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("interaction_type", models.CharField(choices=[("note", "Note"), ("call", "Call"), ("message", "Message"), ("meeting", "Meeting"), ("visit", "Visit"), ("other", "Other")], default="note", max_length=16)),
                ("channel", models.CharField(choices=[("phone", "Phone"), ("email", "Email"), ("whatsapp", "WhatsApp"), ("in_person", "In person"), ("website", "Website"), ("other", "Other")], default="other", max_length=16)),
                ("direction", models.CharField(choices=[("inbound", "Inbound"), ("outbound", "Outbound"), ("internal", "Internal")], default="internal", max_length=16)),
                ("subject", models.CharField(blank=True, max_length=255)),
                ("summary", models.TextField()),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_interactions", to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_interactions", to="organizations.company")),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="crm_interactions", to="customers.customer")),
                ("establishment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="crm_interactions", to="organizations.establishment")),
                ("lead", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="interactions", to="crm.crmlead")),
                ("opportunity", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="interactions", to="crm.crmopportunity")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="crm_interactions", to="organizations.organization")),
            ],
            options={"ordering": ("-occurred_at", "-created_at", "-id")},
        ),
        migrations.AddConstraint(
            model_name="crmsegment",
            constraint=models.UniqueConstraint(fields=("company", "code"), name="crm_segment_unique_code_company"),
        ),
        migrations.AddConstraint(
            model_name="crmsegmentmembership",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("customer__isnull", True), ("lead__isnull", False)), models.Q(("customer__isnull", False), ("lead__isnull", True)), _connector="OR"), name="crm_segment_member_exactly_one_target"),
        ),
        migrations.AddConstraint(
            model_name="crmsegmentmembership",
            constraint=models.UniqueConstraint(condition=models.Q(("lead__isnull", False)), fields=("segment", "lead"), name="crm_segment_member_unique_lead"),
        ),
        migrations.AddConstraint(
            model_name="crmsegmentmembership",
            constraint=models.UniqueConstraint(condition=models.Q(("customer__isnull", False)), fields=("segment", "customer"), name="crm_segment_member_unique_customer"),
        ),
        migrations.AddConstraint(
            model_name="crmfollowup",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("customer__isnull", True), ("lead__isnull", False), ("opportunity__isnull", True)), models.Q(("customer__isnull", True), ("lead__isnull", True), ("opportunity__isnull", False)), models.Q(("customer__isnull", False), ("lead__isnull", True), ("opportunity__isnull", True)), _connector="OR"), name="crm_followup_exactly_one_target"),
        ),
        migrations.AddIndex(
            model_name="crmfollowup",
            index=models.Index(fields=["company", "status", "due_at"], name="crm_followup_due_idx"),
        ),
        migrations.AddConstraint(
            model_name="crminteraction",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("customer__isnull", True), ("lead__isnull", False), ("opportunity__isnull", True)), models.Q(("customer__isnull", True), ("lead__isnull", True), ("opportunity__isnull", False)), models.Q(("customer__isnull", False), ("lead__isnull", True), ("opportunity__isnull", True)), _connector="OR"), name="crm_interaction_exactly_one_target"),
        ),
        migrations.AddIndex(
            model_name="crminteraction",
            index=models.Index(fields=["company", "occurred_at"], name="crm_interaction_time_idx"),
        ),
    ]
