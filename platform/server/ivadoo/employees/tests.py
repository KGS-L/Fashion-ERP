from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from ivadoo.audit.models import AuditEvent
from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.identity.models import User
from ivadoo.organizations.models import Company, Establishment, Organization

from .models import Employee, EmployeeAssignment, EmployeeContract


class EmployeePhase4Tests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Maison Ivadoo", slug="maison-ivadoo")
        self.company = Company.objects.create(
            organization=self.organization,
            name="Ivadoo Fashion",
            code="ivadoo-fashion",
        )
        self.workshop_a = Establishment.objects.create(
            company=self.company,
            name="Atelier A",
            code="atelier-a",
            site_type=Establishment.SiteType.WORKSHOP,
        )
        self.workshop_b = Establishment.objects.create(
            company=self.company,
            name="Atelier B",
            code="atelier-b",
            site_type=Establishment.SiteType.WORKSHOP,
        )
        self.store = Establishment.objects.create(
            company=self.company,
            name="Boutique",
            code="boutique",
            site_type=Establishment.SiteType.STORE,
        )
        self.user = User.objects.create_user(
            username="manager-a",
            password="test-password",
            organization=self.organization,
        )
        self.contract_user = User.objects.create_user(
            username="hr",
            password="test-password",
            organization=self.organization,
        )

        self.employee_view = Permission.objects.get(code="enterprise.employee.view")
        self.employee_manage = Permission.objects.get(code="enterprise.employee.manage")
        self.contract_view = Permission.objects.get(
            code="enterprise.employee.contract.view"
        )
        self.contract_manage = Permission.objects.get(
            code="enterprise.employee.contract.manage"
        )

        self.manager_role = Role.objects.create(
            organization=self.organization,
            code="atelier-manager",
            name="Atelier manager",
        )
        self.manager_role.permissions.set([self.employee_view, self.employee_manage])
        AccessGrant.objects.create(
            role=self.manager_role,
            user=self.user,
            establishment=self.workshop_a,
        )

        self.hr_role = Role.objects.create(
            organization=self.organization,
            code="hr",
            name="HR",
        )
        self.hr_role.permissions.set(
            [
                self.employee_view,
                self.employee_manage,
                self.contract_view,
                self.contract_manage,
            ]
        )
        AccessGrant.objects.create(role=self.hr_role, user=self.contract_user, company=self.company)

        self.employee_a = Employee.objects.create(
            organization=self.organization,
            company=self.company,
            establishment=self.workshop_b,
            code="EMP-001",
            first_name="Awa",
            last_name="Traore",
            display_name="Awa Traore",
            job_title="Couturiere",
            hire_date=date(2026, 1, 1),
        )
        self.employee_b = Employee.objects.create(
            organization=self.organization,
            company=self.company,
            establishment=self.workshop_b,
            code="EMP-002",
            first_name="Mariam",
            last_name="Ouedraogo",
            display_name="Mariam Ouedraogo",
            job_title="Coupe",
        )
        EmployeeAssignment.objects.create(
            employee=self.employee_a,
            company=self.company,
            establishment=self.workshop_a,
            workshop=self.workshop_a,
            role=self.manager_role,
            title="Couturiere",
            start_date=date(2026, 1, 1),
            is_primary=True,
        )
        self.contract = EmployeeContract.objects.create(
            employee=self.employee_a,
            company=self.company,
            establishment=self.workshop_a,
            reference="CTR-001",
            contract_type=EmployeeContract.ContractType.PERMANENT,
            status=EmployeeContract.Status.ACTIVE,
            job_title="Couturiere",
            start_date=date(2026, 1, 1),
            document_reference="contracts/CTR-001.pdf",
        )

        self.client = APIClient()

    def test_establishment_scope_includes_assignment_and_excludes_unassigned_employee(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/employees/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(str(self.employee_a.id), ids)
        self.assertNotIn(str(self.employee_b.id), ids)

    def test_employee_profile_does_not_embed_sensitive_contract_metadata(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(f"/api/v1/employees/{self.employee_a.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("contracts", response.data)
        self.assertNotIn("document_reference", response.data)
        self.assertNotIn("salary", response.data)

    def test_contract_endpoint_requires_dedicated_contract_permission(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/employees/contracts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

        self.client.force_authenticate(self.contract_user)
        response = self.client.get("/api/v1/employees/contracts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["document_reference"],
            "contracts/CTR-001.pdf",
        )

    def test_non_workshop_establishment_cannot_be_used_as_workshop(self):
        self.client.force_authenticate(self.contract_user)
        response = self.client.post(
            "/api/v1/employees/assignments/",
            {
                "employee_id": str(self.employee_a.id),
                "company_id": str(self.company.id),
                "establishment_id": str(self.store.id),
                "workshop_id": str(self.store.id),
                "role_id": str(self.hr_role.id),
                "title": "Temporary",
                "start_date": "2026-02-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("workshop_id", response.data["error"]["details"])

    def test_employee_creation_is_scoped_and_audited(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/employees/",
            {
                "company_id": str(self.company.id),
                "establishment_id": str(self.workshop_a.id),
                "code": "EMP-003",
                "first_name": "Fatou",
                "last_name": "Kone",
                "display_name": "Fatou Kone",
                "job_title": "Finition",
                "status": "active",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Employee.objects.get(code="EMP-003")
        self.assertEqual(created.organization_id, self.organization.id)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="enterprise.employee.create",
                object_id=str(created.id),
            ).exists()
        )

    def test_contract_model_has_no_payroll_fields(self):
        field_names = {field.name for field in EmployeeContract._meta.get_fields()}
        self.assertNotIn("salary", field_names)
        self.assertNotIn("wage", field_names)
        self.assertNotIn("payroll", field_names)
