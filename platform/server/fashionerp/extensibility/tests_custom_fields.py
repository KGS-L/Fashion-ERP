from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from fashionerp.authorization.services import grant_organization_admin
from fashionerp.customers.models import Customer
from fashionerp.identity.services import create_api_session
from fashionerp.organizations.models import Company, Organization

from .custom_fields import normalize_custom_values, save_custom_values
from .models import CustomFieldDefinition, CustomObjectData


class CustomFieldApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Tenant A", slug="tenant-a")
        self.user = get_user_model().objects.create_user(
            username="tenant-a.admin",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        grant_organization_admin(user=self.user)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_admin_can_create_custom_field_definition(self):
        response = self.client.post(
            "/api/v1/platform/custom-fields/",
            {
                "model_key": "customers.customer",
                "key": "x_uniform_size",
                "label": "Uniform size",
                "field_type": "selection",
                "options": ["S", "M", "L", "XL"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["key"], "x_uniform_size")

    def test_custom_field_key_must_use_reserved_prefix(self):
        response = self.client.post(
            "/api/v1/platform/custom-fields/",
            {
                "model_key": "customers.customer",
                "key": "display_name",
                "label": "Bad override",
                "field_type": "text",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_model_and_key_identity_cannot_be_changed(self):
        definition = CustomFieldDefinition.objects.create(
            organization=self.organization,
            model_key="customers.customer",
            key="x_uniform_size",
            label="Uniform size",
            field_type="text",
            created_by=self.user,
        )
        response = self.client.patch(
            f"/api/v1/platform/custom-fields/{definition.id}/",
            {"key": "x_other"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CustomObjectDataTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Tenant A", slug="tenant-a")
        self.company = Company.objects.create(
            organization=self.organization,
            name="Company A",
            code="company-a",
        )
        self.user = get_user_model().objects.create_user(
            username="tenant-a.admin",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="C-001",
            display_name="Customer One",
        )
        CustomFieldDefinition.objects.create(
            organization=self.organization,
            model_key="customers.customer",
            key="x_uniform_size",
            label="Uniform size",
            field_type="selection",
            options=["S", "M", "L"],
            created_by=self.user,
        )

    def test_custom_values_are_normalized_and_stored_sidecar(self):
        record = save_custom_values(
            organization=self.organization,
            model_key="customers.customer",
            object_id=self.customer.id,
            values={"x_uniform_size": "M"},
            actor=self.user,
        )
        self.assertEqual(record.values, {"x_uniform_size": "M"})
        self.assertEqual(CustomObjectData.objects.count(), 1)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.display_name, "Customer One")

    def test_unknown_custom_field_is_rejected(self):
        with self.assertRaises(ValidationError):
            normalize_custom_values(
                organization=self.organization,
                model_key="customers.customer",
                values={"x_missing": "value"},
            )

    def test_inactive_definition_preserves_existing_values_but_rejects_new_write(self):
        definition = CustomFieldDefinition.objects.get(key="x_uniform_size")
        save_custom_values(
            organization=self.organization,
            model_key="customers.customer",
            object_id=self.customer.id,
            values={"x_uniform_size": "M"},
            actor=self.user,
        )
        definition.is_active = False
        definition.save(update_fields=("is_active", "updated_at"))

        with self.assertRaises(ValidationError):
            save_custom_values(
                organization=self.organization,
                model_key="customers.customer",
                object_id=self.customer.id,
                values={"x_uniform_size": "L"},
                actor=self.user,
            )
        self.assertEqual(
            CustomObjectData.objects.get().values["x_uniform_size"],
            "M",
        )
