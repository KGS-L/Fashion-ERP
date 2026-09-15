from django.test import SimpleTestCase, TestCase
from django.urls import resolve
from rest_framework.test import APITestCase

from ivadoo.authorization.models import Permission
from ivadoo.purchases.procurement_serializers import PurchaseOrderSerializer


class Phase3RouteContractTests(SimpleTestCase):
    def test_phase3_resource_roots_are_registered_under_api_v1(self):
        paths = (
            "/api/v1/inventory/warehouses/",
            "/api/v1/purchases/purchase-orders/",
            "/api/v1/manufacturing/orders/",
            "/api/v1/quality/inspections/",
            "/api/v1/delivery/deliveries/",
            "/api/v1/operations/approval-rules/",
        )
        for path in paths:
            with self.subTest(path=path):
                match = resolve(path)
                self.assertIsNotNone(match.func)


class Phase3PermissionContractTests(TestCase):
    def test_each_phase3_domain_has_explicit_permissions(self):
        for module in ("inventory", "purchase", "manufacturing", "quality", "delivery", "operations"):
            with self.subTest(module=module):
                self.assertTrue(
                    Permission.objects.filter(module=module).exists(),
                    f"Missing seeded RBAC permissions for Phase 3 module {module}",
                )

    def test_purchase_order_status_cannot_be_written_through_resource_serializer(self):
        serializer = PurchaseOrderSerializer()
        self.assertTrue(serializer.fields["status"].read_only)
        self.assertTrue(serializer.fields["approved_by_id"].read_only)
        self.assertTrue(serializer.fields["approved_at"].read_only)


class Phase3AuthenticationContractTests(APITestCase):
    def test_operational_resource_roots_require_authentication(self):
        for path in (
            "/api/v1/inventory/warehouses/",
            "/api/v1/purchases/purchase-orders/",
            "/api/v1/manufacturing/orders/",
            "/api/v1/quality/inspections/",
            "/api/v1/delivery/deliveries/",
            "/api/v1/operations/approval-rules/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertIn(response.status_code, (401, 403))
