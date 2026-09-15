from io import BytesIO
import json

from django.contrib.auth import get_user_model
from openpyxl import Workbook
from rest_framework import status
from rest_framework.test import APITestCase

from fashionerp.authorization.services import grant_organization_admin
from fashionerp.customers.models import Customer
from fashionerp.identity.services import create_api_session
from fashionerp.organizations.models import Company, Organization

from .models import CustomFieldDefinition, CustomObjectData


class GenericDataIoTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Tenant A", slug="tenant-a")
        self.company = Company.objects.create(organization=self.organization, name="Company A", code="company-a")
        self.user = get_user_model().objects.create_user(
            username="tenant-a.admin",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        grant_organization_admin(user=self.user)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        CustomFieldDefinition.objects.create(
            organization=self.organization,
            model_key="customers.customer",
            key="x_uniform_size",
            label="Uniform size",
            field_type="selection",
            options=["S", "M", "L"],
            created_by=self.user,
        )

    def _csv(self, content):
        return BytesIO(content.encode("utf-8"))

    def test_csv_preview_then_commit_uses_serializer_and_custom_fields(self):
        payload = "Company,Code,Name,Size\n%s,C-001,Ada,M\n" % self.company.id
        mapping = json.dumps(
            {
                "Company": "company_id",
                "Code": "code",
                "Name": "display_name",
                "Size": "x_uniform_size",
            }
        )
        preview_file = self._csv(payload)
        preview_file.name = "customers.csv"
        response = self.client.post(
            "/api/v1/platform/data/import/",
            {"resource": "customers.customer", "file": preview_file, "mapping": mapping, "mode": "create", "commit": "false"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["counts"]["errors"], 0)
        self.assertEqual(Customer.objects.count(), 0)

        commit_file = self._csv(payload)
        commit_file.name = "customers.csv"
        committed = self.client.post(
            "/api/v1/platform/data/import/",
            {"resource": "customers.customer", "file": commit_file, "mapping": mapping, "mode": "create", "commit": "true"},
            format="multipart",
        )
        self.assertEqual(committed.status_code, status.HTTP_200_OK)
        self.assertTrue(committed.data["commit"])
        customer = Customer.objects.get(code="C-001")
        custom = CustomObjectData.objects.get(object_id=customer.id)
        self.assertEqual(custom.values["x_uniform_size"], "M")

    def test_validation_error_prevents_all_writes(self):
        payload = "Company,Code,Name,Size\n%s,C-001,Ada,M\n%s,C-002,Bob,INVALID\n" % (self.company.id, self.company.id)
        uploaded = self._csv(payload)
        uploaded.name = "customers.csv"
        response = self.client.post(
            "/api/v1/platform/data/import/",
            {
                "resource": "customers.customer",
                "file": uploaded,
                "mapping": json.dumps({"Company": "company_id", "Code": "code", "Name": "display_name", "Size": "x_uniform_size"}),
                "mode": "create",
                "commit": "true",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Customer.objects.count(), 0)

    def test_xlsx_preview_is_supported(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Company", "Code", "Name"])
        sheet.append([str(self.company.id), "C-001", "Ada"])
        payload = BytesIO()
        workbook.save(payload)
        payload.seek(0)
        payload.name = "customers.xlsx"
        response = self.client.post(
            "/api/v1/platform/data/import/",
            {
                "resource": "customers.customer",
                "file": payload,
                "mapping": json.dumps({"Company": "company_id", "Code": "code", "Name": "display_name"}),
                "mode": "create",
                "commit": "false",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["counts"]["valid"], 1)

    def test_export_respects_resource_and_returns_csv(self):
        Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="C-001",
            display_name="Ada",
        )
        response = self.client.get(
            "/api/v1/platform/data/export/?resource=customers.customer&output_format=csv&fields=code,display_name"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("C-001,Ada", response.content.decode("utf-8"))
