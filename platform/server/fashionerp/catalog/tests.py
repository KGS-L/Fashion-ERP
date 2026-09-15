from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from fashionerp.authorization.models import AccessGrant, Permission, Role
from fashionerp.identity.models import User
from fashionerp.identity.services import create_api_session
from fashionerp.internationalization.models import UnitOfMeasure
from fashionerp.organizations.models import Company, Organization

from .models import Product


class ProductCatalogApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Catalog", slug="catalog")
        self.company = Company.objects.create(organization=self.organization, name="Maison", code="catalog-maison")
        self.user = User.objects.create_user(username="catalog.user", password="Strong-Test-Password-42!", organization=self.organization)
        role = Role.objects.create(organization=self.organization, code="catalog-manager", name="Catalog manager", is_active=True)
        role.permissions.set(Permission.objects.filter(code__in=("fashion.product.view", "fashion.product.manage")))
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.meter = UnitOfMeasure.objects.create(organization=self.organization, code="catalog-m", name="Meter", symbol="m", category="length", ratio_to_base=Decimal("1"), rounding=Decimal("0.01"))

    def test_create_fabric_product_and_variant_attributes(self):
        product = self.client.post("/api/v1/products/", {
            "company_id": str(self.company.id), "code": "wax-premium", "name": "Wax Premium",
            "product_type": "fabric", "unit_id": str(self.meter.id),
            "fashion_metadata": {"composition": "cotton", "width_cm": 120},
        }, format="json")
        self.assertEqual(product.status_code, status.HTTP_201_CREATED)

        color = self.client.post("/api/v1/products/attributes/", {
            "code": "color", "name": "Color",
            "values": [{"code": "indigo", "value": "Indigo"}],
        }, format="json")
        self.assertEqual(color.status_code, status.HTTP_201_CREATED)
        value_id = color.data["values"][0]["id"]

        variant = self.client.post(f"/api/v1/products/{product.data['id']}/variants/", {
            "sku": "WAX-PRE-IND", "barcode": "1234567890123",
            "attribute_value_ids": [value_id],
        }, format="json")
        self.assertEqual(variant.status_code, status.HTTP_201_CREATED)
        self.assertEqual(variant.data["sku"], "WAX-PRE-IND")

    def test_supports_all_product_types_from_phase_two_scope(self):
        types = {choice for choice, _ in Product.ProductType.choices}
        self.assertEqual(types, {"finished_good", "fabric", "accessory", "service", "packaging", "waste"})

