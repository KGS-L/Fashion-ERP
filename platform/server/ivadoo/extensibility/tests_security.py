from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.authorization.services import ensure_foundation_permission_catalog, grant_organization_admin
from ivadoo.customers.models import Customer
from ivadoo.identity.services import create_api_session
from ivadoo.organizations.models import Company, Organization

from .custom_fields import save_custom_values
from .models import CustomFieldDefinition


class CustomizationSecurityTests(APITestCase):
    def setUp(self):
        ensure_foundation_permission_catalog()
        self.organization = Organization.objects.create(name="Tenant A", slug="tenant-a")
        self.company = Company.objects.create(
            organization=self.organization,
            name="Company A",
            code="company-a",
        )
        self.admin = get_user_model().objects.create_user(
            username="tenant-a.admin",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        grant_organization_admin(user=self.admin)
        self.customer = Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="C-001",
            display_name="Customer One",
        )

    def test_sensitive_field_requires_explicit_permissions(self):
        _, token = create_api_session(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.post(
            "/api/v1/platform/custom-fields/",
            {
                "model_key": "customers.customer",
                "key": "x_private_note",
                "label": "Private note",
                "field_type": "text",
                "is_sensitive": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_organization_reference_is_rejected(self):
        CustomFieldDefinition.objects.create(
            organization=self.organization,
            model_key="customers.customer",
            key="x_related_customer",
            label="Related customer",
            field_type="reference",
            validation={"target_model": "customers.customer"},
            created_by=self.admin,
        )
        foreign_id = Customer._meta.pk.to_python("00000000-0000-0000-0000-000000000123")
        with self.assertRaises(ValidationError):
            save_custom_values(
                organization=self.organization,
                model_key="customers.customer",
                object_id=self.customer.id,
                values={"x_related_customer": foreign_id},
                actor=self.admin,
            )

    def test_field_permission_cannot_expand_object_access(self):
        restricted = Permission.objects.get(code="fashion.customer.view")
        manage = Permission.objects.get(code="fashion.customer.manage")
        role = Role.objects.create(
            organization=self.organization,
            code="company-customer-reader",
            name="Company customer reader",
        )
        role.permissions.add(restricted, manage)
        user = get_user_model().objects.create_user(
            username="company.reader",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        AccessGrant.objects.create(user=user, role=role, company=self.company)
        _, token = create_api_session(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/v1/platform/metadata/models/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        keys = {item["key"] for item in response.data["models"]}
        self.assertIn("customers.customer", keys)

    def test_custom_data_endpoint_obeys_model_scope(self):
        definition = CustomFieldDefinition.objects.create(
            organization=self.organization,
            model_key="customers.customer",
            key="x_uniform_size",
            label="Uniform size",
            field_type="text",
            created_by=self.admin,
        )
        self.assertIsNotNone(definition.id)
        _, token = create_api_session(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.patch(
            f"/api/v1/platform/custom-data/customers.customer/{self.customer.id}/",
            {"values": {"x_uniform_size": "M"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["values"]["x_uniform_size"], "M")
        self.assertEqual(response.data["version"], 1)
