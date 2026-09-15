import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


def add_performance_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    for code, action, name in (
        (
            "enterprise.employee.performance.view",
            "employee.performance.view",
            "View employee productivity",
        ),
        (
            "enterprise.employee.performance.manage",
            "employee.performance.manage",
            "Generate employee productivity",
        ),
        (
            "enterprise.employee.commission.view",
            "employee.commission.view",
            "View employee commissions",
        ),
        (
            "enterprise.employee.commission.manage",
            "employee.commission.manage",
            "Manage employee commission rules and calculations",
        ),
    ):
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "enterprise", "action": action, "name": name},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0002_work_planning_attendance_tasks_time"),
        ("internationalization", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductivitySnapshot",
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
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("assigned_tasks", models.PositiveIntegerField(default=0)),
                ("completed_tasks", models.PositiveIntegerField(default=0)),
                (
                    "task_completion_rate",
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal("0"),
                        max_digits=7,
                    ),
                ),
                ("tracked_minutes", models.PositiveIntegerField(default=0)),
                ("linked_operation_count", models.PositiveIntegerField(default=0)),
                (
                    "quantity_completion_rate",
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal("0"),
                        max_digits=7,
                    ),
                ),
                ("formula_version", models.CharField(default="v1", max_length=16)),
                ("source_fingerprint", models.CharField(max_length=64)),
                ("source_summary", models.JSONField(default=dict)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_productivity_snapshots",
                        to="organizations.company",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="productivity_snapshots",
                        to="employees.employee",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_productivity_snapshots",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "generated_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="generated_productivity_snapshots",
                        to="identity.user",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"site_type__in": ("workshop", "mixed")},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_workshop_productivity_snapshots",
                        to="organizations.establishment",
                    ),
                ),
            ],
            options={
                "ordering": ("-period_end", "employee__display_name", "-generated_at")
            },
        ),
        migrations.CreateModel(
            name="CommissionRule",
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
                    "basis",
                    models.CharField(
                        choices=[
                            ("completed_task", "Completed task"),
                            ("tracked_hour", "Tracked hour"),
                        ],
                        max_length=24,
                    ),
                ),
                (
                    "rate",
                    models.DecimalField(
                        decimal_places=6,
                        max_digits=18,
                        validators=[MinValueValidator(Decimal("0"))],
                    ),
                ),
                ("active_from", models.DateField(blank=True, null=True)),
                ("active_until", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_commission_rules",
                        to="organizations.company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_employee_commission_rules",
                        to="identity.user",
                    ),
                ),
                (
                    "currency",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_commission_rules",
                        to="internationalization.currency",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="commission_rules",
                        to="employees.employee",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_commission_rules",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_commission_rules",
                        to="organizations.organization",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"site_type__in": ("workshop", "mixed")},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_workshop_commission_rules",
                        to="organizations.establishment",
                    ),
                ),
            ],
            options={"ordering": ("company__name", "code")},
        ),
        migrations.CreateModel(
            name="CommissionCalculation",
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
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                (
                    "basis_quantity",
                    models.DecimalField(decimal_places=6, max_digits=18),
                ),
                (
                    "rate_snapshot",
                    models.DecimalField(decimal_places=6, max_digits=18),
                ),
                ("amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("formula_version", models.CharField(default="v1", max_length=16)),
                ("source_fingerprint", models.CharField(max_length=64)),
                ("rule_snapshot", models.JSONField(default=dict)),
                ("source_summary", models.JSONField(default=dict)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_commission_calculations",
                        to="organizations.company",
                    ),
                ),
                (
                    "currency",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_commission_calculations",
                        to="internationalization.currency",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="commission_calculations",
                        to="employees.employee",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_commission_calculations",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "generated_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="generated_employee_commissions",
                        to="identity.user",
                    ),
                ),
                (
                    "rule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="calculations",
                        to="employees.commissionrule",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"site_type__in": ("workshop", "mixed")},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_workshop_commission_calculations",
                        to="organizations.establishment",
                    ),
                ),
            ],
            options={
                "ordering": ("-period_end", "employee__display_name", "-generated_at")
            },
        ),
        migrations.AddConstraint(
            model_name="productivitysnapshot",
            constraint=models.CheckConstraint(
                condition=models.Q(("period_end__gte", models.F("period_start"))),
                name="employee_productivity_period_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="productivitysnapshot",
            constraint=models.CheckConstraint(
                condition=models.Q(("completed_tasks__lte", models.F("assigned_tasks"))),
                name="employee_productivity_completed_lte_assigned",
            ),
        ),
        migrations.AddConstraint(
            model_name="productivitysnapshot",
            constraint=models.UniqueConstraint(
                fields=(
                    "employee",
                    "company",
                    "establishment",
                    "workshop",
                    "period_start",
                    "period_end",
                    "formula_version",
                    "source_fingerprint",
                ),
                name="employee_productivity_snapshot_source_unique",
                nulls_distinct=False,
            ),
        ),
        migrations.AddConstraint(
            model_name="commissionrule",
            constraint=models.UniqueConstraint(
                fields=("company", "code"),
                name="employee_commission_rule_code_company_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="commissionrule",
            constraint=models.CheckConstraint(
                condition=models.Q(("rate__gte", 0)),
                name="employee_commission_rule_rate_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="commissionrule",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("active_until__isnull", True))
                    | models.Q(("active_from__isnull", True))
                    | models.Q(("active_until__gte", models.F("active_from")))
                ),
                name="employee_commission_rule_period_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="commissioncalculation",
            constraint=models.CheckConstraint(
                condition=models.Q(("period_end__gte", models.F("period_start"))),
                name="employee_commission_calculation_period_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="commissioncalculation",
            constraint=models.CheckConstraint(
                condition=models.Q(("basis_quantity__gte", 0)),
                name="employee_commission_basis_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="commissioncalculation",
            constraint=models.CheckConstraint(
                condition=models.Q(("rate_snapshot__gte", 0)),
                name="employee_commission_rate_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="commissioncalculation",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gte", 0)),
                name="employee_commission_amount_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="commissioncalculation",
            constraint=models.UniqueConstraint(
                fields=(
                    "rule",
                    "employee",
                    "period_start",
                    "period_end",
                    "formula_version",
                    "source_fingerprint",
                ),
                name="employee_commission_calculation_source_unique",
            ),
        ),
        migrations.RunPython(add_performance_permissions, migrations.RunPython.noop),
    ]
