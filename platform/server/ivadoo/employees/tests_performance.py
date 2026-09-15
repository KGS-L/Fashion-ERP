from datetime import date, datetime, timezone
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import Currency
from ivadoo.organizations.models import Company, Establishment, Organization

from .models import (
    CommissionCalculation,
    CommissionRule,
    Employee,
    EmployeeTask,
    EmployeeTimeEntry,
    ProductivitySnapshot,
)
from .performance_services import calculate_commission, generate_productivity_snapshot


class EmployeePerformanceApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Performance Org",
            slug="performance-org",
        )
        self.currency = Currency.objects.create(
            code="XOF",
            name="West African CFA franc",
            symbol="FCFA",
            decimal_places=0,
            rounding=Decimal("1"),
        )
        self.company = Company.objects.create(
            organization=self.organization,
            name="Performance Company",
            code="performance-company",
            functional_currency=self.currency,
        )
        self.workshop = Establishment.objects.create(
            company=self.company,
            name="Main Workshop",
            code="main-workshop",
            site_type=Establishment.SiteType.WORKSHOP,
            timezone="UTC",
        )
        self.employee = Employee.objects.create(
            organization=self.organization,
            company=self.company,
            establishment=self.workshop,
            code="EMP-001",
            first_name="Awa",
            last_name="Traore",
            display_name="Awa Traore",
        )
        self.user = User.objects.create_user(
            username="performance.manager",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        permission_codes = (
            "enterprise.employee.performance.view",
            "enterprise.employee.performance.manage",
            "enterprise.employee.commission.view",
            "enterprise.employee.commission.manage",
        )
        self.role = Role.objects.create(
            organization=self.organization,
            code="performance-manager",
            name="Performance manager",
            is_active=True,
        )
        self.role.permissions.set(
            Permission.objects.filter(code__in=permission_codes)
        )
        AccessGrant.objects.create(
            user=self.user,
            role=self.role,
            company=self.company,
        )
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.period_start = date(2026, 9, 15)
        self.period_end = date(2026, 9, 15)
        self.done_task = EmployeeTask.objects.create(
            employee=self.employee,
            company=self.company,
            establishment=self.workshop,
            workshop=self.workshop,
            title="Finish jacket",
            status=EmployeeTask.Status.DONE,
            planned_start=datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 9, 15, 11, 0, tzinfo=timezone.utc),
            created_by=self.user,
        )
        self.pending_task = EmployeeTask.objects.create(
            employee=self.employee,
            company=self.company,
            establishment=self.workshop,
            workshop=self.workshop,
            title="Prepare trousers",
            status=EmployeeTask.Status.PENDING,
            planned_start=datetime(2026, 9, 15, 13, 0, tzinfo=timezone.utc),
            created_by=self.user,
        )
        self.time_entry = EmployeeTimeEntry.objects.create(
            employee=self.employee,
            task=self.done_task,
            company=self.company,
            establishment=self.workshop,
            workshop=self.workshop,
            started_at=datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 9, 15, 9, 30, tzinfo=timezone.utc),
            duration_minutes=90,
            source=EmployeeTimeEntry.Source.MANUAL,
            recorded_by=self.user,
        )

    def test_productivity_generation_is_explainable_and_idempotent(self):
        payload = {
            "employee_id": str(self.employee.id),
            "company_id": str(self.company.id),
            "establishment_id": str(self.workshop.id),
            "workshop_id": str(self.workshop.id),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
        }
        response = self.client.post(
            "/api/v1/employees/productivity/actions/generate/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["assigned_tasks"], 2)
        self.assertEqual(response.data["completed_tasks"], 1)
        self.assertEqual(Decimal(response.data["task_completion_rate"]), Decimal("50.0000"))
        self.assertEqual(response.data["tracked_minutes"], 90)
        self.assertEqual(response.data["formula_version"], ProductivitySnapshot.FORMULA_VERSION)
        self.assertEqual(response.data["source_summary"]["timezone"], "UTC")
        self.assertEqual(len(response.data["source_summary"]["tasks"]), 2)
        self.assertEqual(len(response.data["source_summary"]["time_entries"]), 1)

        second = self.client.post(
            "/api/v1/employees/productivity/actions/generate/",
            payload,
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED, second.data)
        self.assertEqual(second.data["id"], response.data["id"])
        self.assertEqual(ProductivitySnapshot.objects.count(), 1)

    def test_completed_task_commission_is_reproducible_and_snapshotted(self):
        rule_response = self.client.post(
            "/api/v1/employees/commission-rules/",
            {
                "company_id": str(self.company.id),
                "establishment_id": str(self.workshop.id),
                "workshop_id": str(self.workshop.id),
                "employee_id": str(self.employee.id),
                "code": "task-bonus",
                "name": "Completed task bonus",
                "basis": CommissionRule.Basis.COMPLETED_TASK,
                "rate": "1000.000000",
                "currency_code": self.currency.code,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(rule_response.status_code, status.HTTP_201_CREATED, rule_response.data)

        calculate = self.client.post(
            "/api/v1/employees/commissions/actions/calculate/",
            {
                "rule_id": rule_response.data["id"],
                "employee_id": str(self.employee.id),
                "period_start": self.period_start.isoformat(),
                "period_end": self.period_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(calculate.status_code, status.HTTP_201_CREATED, calculate.data)
        self.assertEqual(Decimal(calculate.data["basis_quantity"]), Decimal("1.000000"))
        self.assertEqual(Decimal(calculate.data["rate_snapshot"]), Decimal("1000.000000"))
        self.assertEqual(Decimal(calculate.data["amount"]), Decimal("1000.000000"))
        self.assertEqual(calculate.data["currency_code"], "XOF")
        self.assertEqual(calculate.data["source_summary"]["completed_task_count"], 1)
        self.assertEqual(calculate.data["rule_snapshot"]["basis"], CommissionRule.Basis.COMPLETED_TASK)

        repeated = self.client.post(
            "/api/v1/employees/commissions/actions/calculate/",
            {
                "rule_id": rule_response.data["id"],
                "employee_id": str(self.employee.id),
                "period_start": self.period_start.isoformat(),
                "period_end": self.period_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(repeated.status_code, status.HTTP_201_CREATED, repeated.data)
        self.assertEqual(repeated.data["id"], calculate.data["id"])
        self.assertEqual(CommissionCalculation.objects.count(), 1)

    def test_tracked_hour_commission_uses_overlap_minutes(self):
        rule = CommissionRule.objects.create(
            organization=self.organization,
            company=self.company,
            establishment=self.workshop,
            workshop=self.workshop,
            employee=self.employee,
            code="hour-bonus",
            name="Tracked hour bonus",
            basis=CommissionRule.Basis.TRACKED_HOUR,
            rate=Decimal("500"),
            currency=self.currency,
            created_by=self.user,
        )
        calculation = calculate_commission(
            rule=rule,
            employee=self.employee,
            period_start=self.period_start,
            period_end=self.period_end,
            generated_by=self.user,
        )
        self.assertEqual(calculation.basis_quantity, Decimal("1.500000"))
        self.assertEqual(calculation.amount, Decimal("750"))
        self.assertEqual(calculation.source_summary["tracked_minutes"], 90)
        self.assertEqual(calculation.source_summary["tracked_hours"], "1.500000")

    def test_generation_does_not_escape_company_scope(self):
        other_company = Company.objects.create(
            organization=self.organization,
            name="Other Company",
            code="other-company",
            functional_currency=self.currency,
        )
        other_employee = Employee.objects.create(
            organization=self.organization,
            company=other_company,
            code="EMP-OTHER",
            first_name="Binta",
            last_name="Sawadogo",
            display_name="Binta Sawadogo",
        )
        response = self.client.post(
            "/api/v1/employees/productivity/actions/generate/",
            {
                "employee_id": str(other_employee.id),
                "company_id": str(other_company.id),
                "period_start": self.period_start.isoformat(),
                "period_end": self.period_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ProductivitySnapshot.objects.count(), 0)

    def test_inactive_commission_rule_cannot_be_calculated(self):
        rule = CommissionRule.objects.create(
            organization=self.organization,
            company=self.company,
            employee=self.employee,
            code="inactive-bonus",
            name="Inactive bonus",
            basis=CommissionRule.Basis.COMPLETED_TASK,
            rate=Decimal("1000"),
            currency=self.currency,
            is_active=False,
            created_by=self.user,
        )
        response = self.client.post(
            "/api/v1/employees/commissions/actions/calculate/",
            {
                "rule_id": str(rule.id),
                "employee_id": str(self.employee.id),
                "period_start": self.period_start.isoformat(),
                "period_end": self.period_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CommissionCalculation.objects.count(), 0)

    def test_source_change_creates_new_productivity_snapshot(self):
        first = generate_productivity_snapshot(
            employee=self.employee,
            company=self.company,
            establishment=self.workshop,
            workshop=self.workshop,
            period_start=self.period_start,
            period_end=self.period_end,
            generated_by=self.user,
        )
        self.pending_task.status = EmployeeTask.Status.DONE
        self.pending_task.completed_at = datetime(
            2026, 9, 15, 15, 0, tzinfo=timezone.utc
        )
        self.pending_task.save(update_fields=["status", "completed_at", "updated_at"])

        second = generate_productivity_snapshot(
            employee=self.employee,
            company=self.company,
            establishment=self.workshop,
            workshop=self.workshop,
            period_start=self.period_start,
            period_end=self.period_end,
            generated_by=self.user,
        )
        self.assertNotEqual(first.id, second.id)
        self.assertNotEqual(first.source_fingerprint, second.source_fingerprint)
        self.assertEqual(second.completed_tasks, 2)
        self.assertEqual(second.task_completion_rate, Decimal("100.0000"))
