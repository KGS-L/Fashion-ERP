from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from ivadoo.audit.models import AuditEvent
from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.organizations.models import Company, Establishment, Organization
from ivadoo.sales.models import Order

from .models import (
    AttendanceRecord,
    Employee,
    EmployeeSchedule,
    EmployeeTask,
    EmployeeTaskTransition,
    EmployeeTimeEntry,
)


class EmployeeWorkPhase4Tests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Work Org",
            slug="work-org",
        )
        self.company = Company.objects.create(
            organization=self.organization,
            name="Work Company",
            code="work-company",
        )
        self.other_company = Company.objects.create(
            organization=self.organization,
            name="Other Company",
            code="other-company",
        )
        self.workshop_a = Establishment.objects.create(
            company=self.company,
            name="Atelier A",
            code="work-a",
            site_type=Establishment.SiteType.WORKSHOP,
        )
        self.workshop_b = Establishment.objects.create(
            company=self.company,
            name="Atelier B",
            code="work-b",
            site_type=Establishment.SiteType.WORKSHOP,
        )
        self.employee_a = Employee.objects.create(
            organization=self.organization,
            company=self.company,
            establishment=self.workshop_a,
            code="WORK-001",
            first_name="Awa",
            last_name="Kone",
            display_name="Awa Kone",
        )
        self.employee_b = Employee.objects.create(
            organization=self.organization,
            company=self.company,
            establishment=self.workshop_b,
            code="WORK-002",
            first_name="Mariam",
            last_name="Sawadogo",
            display_name="Mariam Sawadogo",
        )
        self.user = User.objects.create_user(
            username="work-manager",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        self.role = Role.objects.create(
            organization=self.organization,
            code="work-manager-role",
            name="Work manager",
        )
        self.role.permissions.set(
            Permission.objects.filter(
                code__in=(
                    "enterprise.employee.work.view",
                    "enterprise.employee.work.manage",
                )
            )
        )
        AccessGrant.objects.create(
            user=self.user,
            role=self.role,
            establishment=self.workshop_a,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.now = timezone.now().replace(microsecond=0)

    def test_workshop_scope_limits_schedule_visibility(self):
        EmployeeSchedule.objects.create(
            employee=self.employee_a,
            company=self.company,
            establishment=self.workshop_a,
            workshop=self.workshop_a,
            label="Morning A",
            starts_at=self.now,
            ends_at=self.now + timedelta(hours=8),
            created_by=self.user,
        )
        EmployeeSchedule.objects.create(
            employee=self.employee_b,
            company=self.company,
            establishment=self.workshop_b,
            workshop=self.workshop_b,
            label="Morning B",
            starts_at=self.now,
            ends_at=self.now + timedelta(hours=8),
            created_by=self.user,
        )

        response = self.client.get("/api/v1/employees/schedules/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["label"], "Morning A")

    def test_task_transition_is_controlled_and_history_is_immutable(self):
        created = self.client.post(
            "/api/v1/employees/tasks/",
            {
                "employee_id": str(self.employee_a.id),
                "company_id": str(self.company.id),
                "establishment_id": str(self.workshop_a.id),
                "workshop_id": str(self.workshop_a.id),
                "title": "Assembler la veste",
                "priority": "high",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        task_id = created.data["id"]

        started = self.client.patch(
            f"/api/v1/employees/tasks/{task_id}/",
            {"status": "in_progress"},
            format="json",
        )
        self.assertEqual(started.status_code, status.HTTP_200_OK, started.data)
        self.assertIsNotNone(started.data["started_at"])

        done = self.client.patch(
            f"/api/v1/employees/tasks/{task_id}/",
            {"status": "done"},
            format="json",
        )
        self.assertEqual(done.status_code, status.HTTP_200_OK, done.data)
        self.assertIsNotNone(done.data["completed_at"])

        invalid = self.client.patch(
            f"/api/v1/employees/tasks/{task_id}/",
            {"status": "in_progress"},
            format="json",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

        transitions = EmployeeTaskTransition.objects.filter(task_id=task_id)
        self.assertEqual(transitions.count(), 3)
        transition = transitions.order_by("occurred_at").last()
        transition.note = "must not mutate"
        with self.assertRaises(Exception):
            transition.save()

    def test_time_duration_is_server_computed_and_invalid_interval_is_rejected(self):
        started_at = self.now
        ended_at = self.now + timedelta(hours=1, minutes=35)
        created = self.client.post(
            "/api/v1/employees/time-entries/",
            {
                "employee_id": str(self.employee_a.id),
                "company_id": str(self.company.id),
                "establishment_id": str(self.workshop_a.id),
                "workshop_id": str(self.workshop_a.id),
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "duration_minutes": 9999,
                "source": "manual",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data["duration_minutes"], 95)
        entry = EmployeeTimeEntry.objects.get(id=created.data["id"])
        self.assertEqual(entry.duration_minutes, 95)

        invalid = self.client.post(
            "/api/v1/employees/time-entries/",
            {
                "employee_id": str(self.employee_a.id),
                "company_id": str(self.company.id),
                "workshop_id": str(self.workshop_a.id),
                "started_at": ended_at.isoformat(),
                "ended_at": started_at.isoformat(),
                "source": "manual",
            },
            format="json",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attendance_is_scoped_traceable_and_audited(self):
        response = self.client.post(
            "/api/v1/employees/attendance/",
            {
                "employee_id": str(self.employee_a.id),
                "company_id": str(self.company.id),
                "establishment_id": str(self.workshop_a.id),
                "workshop_id": str(self.workshop_a.id),
                "attendance_date": date.today().isoformat(),
                "status": "present",
                "check_in_at": self.now.isoformat(),
                "check_out_at": (self.now + timedelta(hours=8)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        attendance = AttendanceRecord.objects.get(id=response.data["id"])
        self.assertEqual(attendance.employee_id, self.employee_a.id)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="enterprise.employee_attendance.create",
                object_id=str(attendance.id),
            ).exists()
        )

    def test_task_can_link_order_but_rejects_order_from_other_company(self):
        customer = Customer.objects.create(
            organization=self.organization,
            company=self.other_company,
            code="other-customer",
            display_name="Other Customer",
        )
        other_order = Order.objects.create(
            organization=self.organization,
            company=self.other_company,
            customer=customer,
            number="SO-OTHER-1",
            status=Order.Status.CONFIRMED,
        )

        response = self.client.post(
            "/api/v1/employees/tasks/",
            {
                "employee_id": str(self.employee_a.id),
                "company_id": str(self.company.id),
                "workshop_id": str(self.workshop_a.id),
                "order_id": str(other_order.id),
                "title": "Wrong company task",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("order_id", response.data["error"]["details"])

    def test_work_models_do_not_introduce_payroll_fields(self):
        for model in (AttendanceRecord, EmployeeTask, EmployeeTimeEntry):
            field_names = {field.name for field in model._meta.get_fields()}
            self.assertNotIn("salary", field_names)
            self.assertNotIn("wage", field_names)
            self.assertNotIn("payroll", field_names)
