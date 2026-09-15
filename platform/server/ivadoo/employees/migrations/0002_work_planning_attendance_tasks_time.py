import uuid

from django.db import migrations, models
import django.db.models.deletion


def add_employee_work_permissions(apps, schema_editor):
    Permission = apps.get_model("authorization", "Permission")
    for code, action, name in (
        ("enterprise.employee.work.view", "employee.work.view", "View employee work planning"),
        (
            "enterprise.employee.work.manage",
            "employee.work.manage",
            "Manage employee work planning",
        ),
    ):
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": "enterprise", "action": action, "name": name},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0001_initial"),
        ("manufacturing", "0003_material_flow_and_output"),
        ("sales", "0003_sales_line_value_constraints"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmployeeSchedule",
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
                ("label", models.CharField(blank=True, max_length=160)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("planned", "Planned"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="planned",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_schedules",
                        to="organizations.company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_employee_schedules",
                        to="identity.user",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="schedules",
                        to="employees.employee",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_schedules",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"site_type__in": ("workshop", "mixed")},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_workshop_schedules",
                        to="organizations.establishment",
                    ),
                ),
            ],
            options={"ordering": ("starts_at", "employee_id")},
        ),
        migrations.CreateModel(
            name="AttendanceRecord",
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
                ("attendance_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("present", "Present"),
                            ("late", "Late"),
                            ("absent", "Absent"),
                            ("excused", "Excused"),
                        ],
                        max_length=16,
                    ),
                ),
                ("check_in_at", models.DateTimeField(blank=True, null=True)),
                ("check_out_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_attendance_records",
                        to="organizations.company",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="attendance_records",
                        to="employees.employee",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_attendance_records",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="recorded_employee_attendance",
                        to="identity.user",
                    ),
                ),
                (
                    "schedule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="attendance_records",
                        to="employees.employeeschedule",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"site_type__in": ("workshop", "mixed")},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_workshop_attendance_records",
                        to="organizations.establishment",
                    ),
                ),
            ],
            options={"ordering": ("-attendance_date", "employee_id", "check_in_at")},
        ),
        migrations.CreateModel(
            name="EmployeeTask",
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
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In progress"),
                            ("blocked", "Blocked"),
                            ("done", "Done"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                (
                    "priority",
                    models.CharField(
                        choices=[
                            ("low", "Low"),
                            ("normal", "Normal"),
                            ("high", "High"),
                            ("urgent", "Urgent"),
                        ],
                        default="normal",
                        max_length=16,
                    ),
                ),
                ("planned_start", models.DateTimeField(blank=True, null=True)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_tasks",
                        to="organizations.company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_employee_tasks",
                        to="identity.user",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tasks",
                        to="employees.employee",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_tasks",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "manufacturing_operation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_tasks",
                        to="manufacturing.manufacturingoperation",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_tasks",
                        to="sales.order",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"site_type__in": ("workshop", "mixed")},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_workshop_tasks",
                        to="organizations.establishment",
                    ),
                ),
            ],
            options={"ordering": ("-priority", "due_at", "created_at")},
        ),
        migrations.CreateModel(
            name="EmployeeTaskTransition",
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
                ("from_status", models.CharField(max_length=16)),
                ("to_status", models.CharField(max_length=16)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_task_transitions",
                        to="identity.user",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="history",
                        to="employees.employeetask",
                    ),
                ),
            ],
            options={"ordering": ("occurred_at", "id")},
        ),
        migrations.CreateModel(
            name="EmployeeTimeEntry",
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
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("duration_minutes", models.PositiveIntegerField(default=0, editable=False)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("timer", "Timer"),
                            ("mobile", "Mobile"),
                        ],
                        default="manual",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_time_entries",
                        to="organizations.company",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="time_entries",
                        to="employees.employee",
                    ),
                ),
                (
                    "establishment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_time_entries",
                        to="organizations.establishment",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="recorded_employee_time_entries",
                        to="identity.user",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="time_entries",
                        to="employees.employeetask",
                    ),
                ),
                (
                    "workshop",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"site_type__in": ("workshop", "mixed")},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_workshop_time_entries",
                        to="organizations.establishment",
                    ),
                ),
            ],
            options={"ordering": ("-started_at", "employee_id")},
        ),
        migrations.AddConstraint(
            model_name="employeeschedule",
            constraint=models.CheckConstraint(
                condition=models.Q(("ends_at__gt", models.F("starts_at"))),
                name="employee_schedule_end_after_start",
            ),
        ),
        migrations.AddConstraint(
            model_name="attendancerecord",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("check_out_at__isnull", True))
                    | models.Q(("check_out_at__gte", models.F("check_in_at")))
                ),
                name="employee_attendance_checkout_after_checkin",
            ),
        ),
        migrations.AddConstraint(
            model_name="employeetimeentry",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("ended_at__isnull", True))
                    | models.Q(("ended_at__gte", models.F("started_at")))
                ),
                name="employee_time_end_after_start",
            ),
        ),
        migrations.RunPython(add_employee_work_permissions, migrations.RunPython.noop),
    ]
