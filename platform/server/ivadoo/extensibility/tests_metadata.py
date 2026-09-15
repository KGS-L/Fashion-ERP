from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import Permission, Role
from ivadoo.authorization.services import grant_organization_admin
from ivadoo.identity.services import create_api_session
from ivadoo.organizations.models import Organization

from .models import CustomFieldDefinition
from .services import set_module_state


class MetadataApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Tenant A", slug="tenant-a")
        self.admin = get_user_model().objects.create_user(
            username="tenant-a.admin",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        grant_organization_admin(user=self.admin)
        _, token = create_api_session(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_metadata_lists_registered_models_and_native_fields(self):
        response = self.client.get("/api/v1/platform/metadata/models/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        models = {item["key"]: item for item in response.data["models"]}
        self.assertIn("customers.customer", models)
        fields = {item["key"]: item for item in models["customers.customer"]["fields"]}
        self.assertIn("display_name", fields)
        self.assertTrue(fields["organization_id"]["protected"])
        self.assertIn("ETag", response)

    def test_active_custom_field_is_part_of_metadata(self):
        CustomFieldDefinition.objects.create(
            organization=self.organization,
            model_key="customers.customer",
            key="x_uniform_size",
            label="Uniform size",
            field_type="text",
            created_by=self.admin,
        )
        response = self.client.get("/api/v1/platform/metadata/models/customers.customer/")
        keys = {item["key"] for item in response.data["fields"]}
        self.assertIn("x_uniform_size", keys)

    def test_disabled_module_is_not_disclosed_by_metadata(self):
        set_module_state(
            organization=self.organization,
            module_code="operations.manufacturing",
            enabled=False,
            actor=self.admin,
        )
        set_module_state(
            organization=self.organization,
            module_code="fashion.sales",
            enabled=False,
            actor=self.admin,
        )
        response = self.client.get("/api/v1/platform/metadata/models/")
        keys = {item["key"] for item in response.data["models"]}
        self.assertNotIn("sales.order", keys)

        detail = self.client.get("/api/v1/platform/metadata/models/sales.order/")
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_etag_supports_conditional_request(self):
        first = self.client.get("/api/v1/platform/metadata/models/")
        etag = first["ETag"]
        second = self.client.get(
            "/api/v1/platform/metadata/models/",
            HTTP_IF_NONE_MATCH=etag,
        )
        self.assertEqual(second.status_code, status.HTTP_304_NOT_MODIFIED)
        self.assertEqual(second["ETag"], etag)
