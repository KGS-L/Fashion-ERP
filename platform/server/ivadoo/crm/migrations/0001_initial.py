import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
import ivadoo.internationalization.validators
from django.conf import settings
from django.db import migrations, models


def add_crm_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    definitions = (
        ("enterprise.crm.view", "enterprise", "crm.view", "View CRM"),
        ("enterprise.crm.manage", "enterprise", "crm.manage", "Manage CRM"),
        ("enterprise.crm.convert", "enterprise", "crm.convert", "Convert CRM prospects"),
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
        ("authorization", "0003_add_i18n_permissions"),
        ("customers", "0001_initial"),
        ("internationalization", "0001_initial"),
        ("organizations", "0003_international_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="CRMPipelineStage",
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
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                ("position", models.PositiveIntegerField(default=10)),
                (
                    "stage_type",
                    models.CharField(
                        choices=[("open", "Open"), ("won", "Won"), ("lost", "Lost")],
                        default="open",
                        max_length=16,
                    ),
                ),
                (
                    "probability",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0")),
                            django.core.validators.MaxValueValidator(Decimal("100")),
                        ],
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_pipeline_stages",
                        to="organizations.company",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_pipeline_stages",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"ordering": ("company__name", "position", "name")},
        ),
        migrations.CreateModel(
            name="CRMSource",
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
                ("code", models.SlugField(max_length=80)),
                ("name", models.CharField(max_length=160)),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("referral", "Referral"),
                            ("website", "Website"),
                            ("social", "Social media"),
                            ("advertising", "Advertising"),
                            ("event", "Event"),
                            ("walk_in", "Walk in"),
                            ("partner", "Partner"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=24,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_sources",
                        to="organizations.company",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_sources",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"ordering": ("company__name", "name", "code")},
        ),
        migrations.CreateModel(
            name="CRMLead",
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
                ("code", models.CharField(max_length=64)),
                (
                    "prospect_type",
                    models.CharField(
                        choices=[("individual", "Individual"), ("company", "Company")],
                        default="individual",
                        max_length=16,
                    ),
                ),
                ("display_name", models.CharField(max_length=255)),
                ("first_name", models.CharField(blank=True, max_length=120)),
                ("last_name", models.CharField(blank=True, max_length=120)),
                ("legal_name", models.CharField(blank=True, max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=64)),
                (
                    "language_code",
                    models.CharField(
                        choices=[
                            ("fr", "Français"),
                            ("en", "English"),
                            ("es", "Español"),
                            ("pt", "Português"),
                            ("ar", "العربية"),
                        ],
                        default="fr",
                        max_length=8,
                        validators=[
                            ivadoo.internationalization.validators.validate_language_code
                        ],
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("qualified", "Qualified"),
                            ("disqualified", "Disqualified"),
                            ("converted", "Converted"),
                        ],
                        default="new",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("converted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_leads",
                        to="organizations.company",
                    ),
                ),
                (
                    "converted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="converted_crm_leads",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "converted_customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="converted_crm_leads",
                        to="customers.customer",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_crm_leads",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_leads",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_leads",
                        to="organizations.organization",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="owned_crm_leads",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="leads",
                        to="crm.crmsource",
                    ),
                ),
            ],
            options={"ordering": ("-created_at", "display_name")},
        ),
        migrations.CreateModel(
            name="CRMOpportunity",
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
                ("code", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "prospect_type",
                    models.CharField(
                        choices=[("individual", "Individual"), ("company", "Company")],
                        default="individual",
                        max_length=16,
                    ),
                ),
                ("contact_name", models.CharField(blank=True, max_length=255)),
                ("legal_name", models.CharField(blank=True, max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=64)),
                (
                    "language_code",
                    models.CharField(
                        choices=[
                            ("fr", "Français"),
                            ("en", "English"),
                            ("es", "Español"),
                            ("pt", "Português"),
                            ("ar", "العربية"),
                        ],
                        default="fr",
                        max_length=8,
                        validators=[
                            ivadoo.internationalization.validators.validate_language_code
                        ],
                    ),
                ),
                (
                    "expected_revenue",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=18,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0"))
                        ],
                    ),
                ),
                (
                    "probability",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0")),
                            django.core.validators.MaxValueValidator(Decimal("100")),
                        ],
                    ),
                ),
                ("expected_close_date", models.DateField(blank=True, null=True)),
                ("converted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_opportunities",
                        to="organizations.company",
                    ),
                ),
                (
                    "converted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="converted_crm_opportunities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_crm_opportunities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "currency",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_opportunities",
                        to="internationalization.currency",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_opportunities",
                        to="customers.customer",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_opportunities",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "lead",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="opportunities",
                        to="crm.crmlead",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_opportunities",
                        to="organizations.organization",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="owned_crm_opportunities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="opportunities",
                        to="crm.crmsource",
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="opportunities",
                        to="crm.crmpipelinestage",
                    ),
                ),
            ],
            options={"ordering": ("stage__position", "-created_at", "title")},
        ),
        migrations.CreateModel(
            name="CRMConversionEvent",
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
                (
                    "source_kind",
                    models.CharField(
                        choices=[("lead", "Lead"), ("opportunity", "Opportunity")],
                        max_length=16,
                    ),
                ),
                ("created_customer", models.BooleanField(default=False)),
                ("source_snapshot", models.JSONField(default=dict)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_conversion_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_conversion_events",
                        to="organizations.company",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_conversion_events",
                        to="customers.customer",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_conversion_events",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "lead",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="conversion_events",
                        to="crm.crmlead",
                    ),
                ),
                (
                    "opportunity",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="conversion_events",
                        to="crm.crmopportunity",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="crm_conversion_events",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"ordering": ("-occurred_at", "-id")},
        ),
        migrations.AddConstraint(
            model_name="crmpipelinestage",
            constraint=models.UniqueConstraint(
                fields=("company", "code"),
                name="crm_stage_unique_code_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="crmpipelinestage",
            constraint=models.UniqueConstraint(
                fields=("company", "position"),
                name="crm_stage_unique_position_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="crmpipelinestage",
            constraint=models.CheckConstraint(
                condition=models.Q(("probability__gte", 0), ("probability__lte", 100)),
                name="crm_stage_probability_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="crmsource",
            constraint=models.UniqueConstraint(
                fields=("company", "code"),
                name="crm_source_unique_code_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="crmlead",
            constraint=models.UniqueConstraint(
                fields=("company", "code"),
                name="crm_lead_unique_code_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="crmopportunity",
            constraint=models.UniqueConstraint(
                fields=("company", "code"),
                name="crm_opportunity_unique_code_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="crmopportunity",
            constraint=models.CheckConstraint(
                condition=models.Q(("expected_revenue__gte", 0)),
                name="crm_opportunity_revenue_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="crmopportunity",
            constraint=models.CheckConstraint(
                condition=models.Q(("probability__gte", 0), ("probability__lte", 100)),
                name="crm_opportunity_probability_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="crmconversionevent",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(lead__isnull=False, opportunity__isnull=True)
                    | models.Q(lead__isnull=True, opportunity__isnull=False)
                ),
                name="crm_conversion_exactly_one_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="crmconversionevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(lead__isnull=False),
                fields=("lead",),
                name="crm_conversion_one_per_lead",
            ),
        ),
        migrations.AddConstraint(
            model_name="crmconversionevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(opportunity__isnull=False),
                fields=("opportunity",),
                name="crm_conversion_one_per_opportunity",
            ),
        ),
        migrations.RunPython(add_crm_permissions, migrations.RunPython.noop),
    ]
