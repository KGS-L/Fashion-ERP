import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def add_employee_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    for code, action, name in (
        ("enterprise.employee.view", "employee.view", "View employees"),
        ("enterprise.employee.manage", "employee.manage", "Manage employees"),
        (
            "enterprise.employee.contract.view",
            "employee.contract.view",
            "View employee contracts",
        ),
        (
            "enterprise.employee.contract.manage",
            "employee.contract.manage",
            "Manage employee contracts",
        ),
    ):
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "enterprise", "action": action, "name": name},
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("authorization", "0003_add_i18n_permissions"),
        ("organizations", "0003_international_settings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Skill",
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
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_skills_catalog",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"ordering": ("name", "code")},
        ),
        migrations.CreateModel(
            name="Employee",
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
                ("first_name", models.CharField(max_length=120)),
                ("last_name", models.CharField(max_length=120)),
                ("display_name", models.CharField(max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=64)),
                ("job_title", models.CharField(blank=True, max_length=160)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("inactive", "Inactive"),
                            ("archived", "Archived"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("hire_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employees",
                        to="organizations.company",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employees",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employees",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="employee_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("display_name", "code")},
        ),
        migrations.CreateModel(
            name="EmployeeSkill",
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
                    "proficiency",
                    models.CharField(
                        choices=[
                            ("beginner", "Beginner"),
                            ("intermediate", "Intermediate"),
                            ("advanced", "Advanced"),
                            ("expert", "Expert"),
                        ],
                        default="intermediate",
                        max_length=16,
                    ),
                ),
                ("is_specialty", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="skills",
                        to="employees.employee",
                    ),
                ),
                (
                    "skill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_links",
                        to="employees.skill",
                    ),
                ),
            ],
            options={"ordering": ("employee_id", "skill__name")},
        ),
        migrations.CreateModel(
            name="EmployeeContract",
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
                ("reference", models.CharField(max_length=80)),
                (
                    "contract_type",
                    models.CharField(
                        choices=[
                            ("permanent", "Permanent"),
                            ("fixed_term", "Fixed term"),
                            ("contractor", "Contractor"),
                            ("internship", "Internship"),
                            ("other", "Other"),
                        ],
                        max_length=24,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("active", "Active"),
                            ("ended", "Ended"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("job_title", models.CharField(blank=True, max_length=160)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("document_reference", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_contracts",
                        to="organizations.company",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contracts",
                        to="employees.employee",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_contracts",
                        to="organizations.establishment",
                    ),
                ),
            ],
            options={"ordering": ("-start_date", "reference")},
        ),
        migrations.CreateModel(
            name="EmployeeAssignment",
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
                ("title", models.CharField(blank=True, max_length=160)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_assignments",
                        to="organizations.company",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="employees.employee",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_assignments",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_assignments",
                        to="authorization.role",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"site_type__in": ("workshop", "mixed")},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_workshop_assignments",
                        to="organizations.establishment",
                    ),
                ),
            ],
            options={"ordering": ("-is_primary", "-start_date", "employee_id")},
        ),
        migrations.AddConstraint(
            model_name="skill",
            constraint=models.UniqueConstraint(
                fields=("organization", "code"),
                name="employee_skill_unique_code_per_organization",
            ),
        ),
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.UniqueConstraint(
                fields=("company", "code"),
                name="employee_unique_code_per_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("end_date__isnull", True))
                    | models.Q(("hire_date__isnull", True))
                    | models.Q(("end_date__gte", models.F("hire_date")))
                ),
                name="employee_end_date_not_before_hire_date",
            ),
        ),
        migrations.AddConstraint(
            model_name="employeeskill",
            constraint=models.UniqueConstraint(
                fields=("employee", "skill"),
                name="employee_skill_unique_link",
            ),
        ),
        migrations.AddConstraint(
            model_name="employeecontract",
            constraint=models.UniqueConstraint(
                fields=("company", "reference"),
                name="employee_contract_unique_reference_per_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="employeecontract",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("end_date__isnull", True))
                    | models.Q(("end_date__gte", models.F("start_date")))
                ),
                name="employee_contract_end_not_before_start",
            ),
        ),
        migrations.AddConstraint(
            model_name="employeeassignment",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("end_date__isnull", True))
                    | models.Q(("end_date__gte", models.F("start_date")))
                ),
                name="employee_assignment_end_not_before_start",
            ),
        ),
        migrations.RunPython(add_employee_permissions, migrations.RunPython.noop),
    ]
