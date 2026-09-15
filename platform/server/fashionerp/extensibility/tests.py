from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase

from fashionerp.authorization.services import grant_organization_admin
from fashionerp.identity.services import create_api_session
from fashionerp.organizations.models import Organization

from .models import ModuleInstallation
from .services import is_module_enabled, set_module_state


class ModuleRegistryTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Tenant A",
            slug="tenant-a",
        )
        self.user = get_user_model().objects.create_user(
            username="tenant-a.admin",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        grant_organization_admin(user=self.user)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_existing_phase_two_modules_are_enabled_by_default(self):
        self.assertTrue(is_module_enabled(self.organization, "fashion.customers"))
        self.assertTrue(is_module_enabled(self.organization, "fashion.catalog"))
        self.assertTrue(is_module_enabled(self.organization, "fashion.sales"))

    def test_required_foundation_cannot_be_disabled(self):
        with self.assertRaises(ValidationError):
            set_module_state(
                organization=self.organization,
                module_code="foundation",
                enabled=False,
                actor=self.user,
            )

    def test_dependency_blocks_disable(self):
        with self.assertRaises(ValidationError):
            set_module_state(
                organization=self.organization,
                module_code="fashion.catalog",
                enabled=False,
                actor=self.user,
            )

    def test_disabled_module_is_enforced_server_side(self):
        set_module_state(
            organization=self.organization,
            module_code="fashion.sales",
            enabled=False,
            actor=self.user,
        )
        self.assertFalse(is_module_enabled(self.organization, "fashion.sales"))
        installation = ModuleInstallation.objects.get(
            organization=self.organization,
            module_code="fashion.sales",
        )
        self.assertEqual(installation.state, ModuleInstallation.State.DISABLED)

        response = self.client.get("/api/v1/sales/orders/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_module_registry_api_lists_effective_state(self):
        response = self.client.get("/api/v1/platform/modules/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = {item["code"] for item in response.data}
        self.assertIn("foundation", codes)
        self.assertIn("fashion.sales", codes)
