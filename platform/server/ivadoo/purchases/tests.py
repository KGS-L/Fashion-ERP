from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import Product
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import Currency, UnitOfMeasure
from ivadoo.organizations.models import Company, Organization

from .models import Supplier


class SupplierApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Purchasing", slug="purchasing")
        self.company = Company.objects.create(organization=self.organization, name="Maison", code="maison")
        self.other_company = Company.objects.create(organization=self.organization, name="Atelier B", code="atelier-b")
        self.currency = Currency.objects.create(code="XOF", name="West African CFA franc", symbol="FCFA", decimal_places=0, rounding=Decimal("1"))
        self.unit = UnitOfMeasure.objects.create(organization=self.organization, code="m", name="Meter", symbol="m", category="length", ratio_to_base=Decimal("1"), rounding=Decimal("0.01"))
        self.user = User.objects.create_user(username="purchase.manager", password="Strong-Test-Password-42!", organization=self.organization)
        role = Role.objects.create(organization=self.organization, code="purchase-manager", name="Purchase manager", is_active=True)
        role.permissions.set(Permission.objects.filter(code__in=("purchase.supplier.view", "purchase.supplier.manage")))
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_supplier_contacts_addresses_and_product_reference(self):
        supplier = self.client.post("/api/v1/purchases/suppliers/", {"company_id": str(self.company.id), "code": "faso-textile", "name": "Faso Textile", "currency_code": "XOF", "language_code": "fr", "lead_time_days": 5, "minimum_order_amount": "50000.0000"}, format="json")
        self.assertEqual(supplier.status_code, status.HTTP_201_CREATED)
        supplier_id = supplier.data["id"]
        contact = self.client.post(f"/api/v1/purchases/suppliers/{supplier_id}/contacts/", {"name": "Awa Ouedraogo", "role": "Commercial", "email": "awa@example.test", "is_primary": True}, format="json")
        self.assertEqual(contact.status_code, status.HTTP_201_CREATED)
        address = self.client.post(f"/api/v1/purchases/suppliers/{supplier_id}/addresses/", {"label": "Principal", "address_line1": "Zone industrielle", "city": "Ouagadougou", "country_code": "BF", "is_primary": True}, format="json")
        self.assertEqual(address.status_code, status.HTTP_201_CREATED)
        product = Product.objects.create(organization=self.organization, company=self.company, code="wax", name="Wax", product_type=Product.ProductType.FABRIC, unit=self.unit)
        supplier_product = self.client.post(f"/api/v1/purchases/suppliers/{supplier_id}/products/", {"product_id": str(product.id), "unit_id": str(self.unit.id), "currency_code": "XOF", "supplier_sku": "FT-WAX", "lead_time_days": 4, "minimum_quantity": "10.0000", "last_unit_price": "2500.0000", "is_preferred": True}, format="json")
        self.assertEqual(supplier_product.status_code, status.HTTP_201_CREATED)
        detail = self.client.get(f"/api/v1/purchases/suppliers/{supplier_id}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detail.data["contacts"]), 1)
        self.assertEqual(len(detail.data["addresses"]), 1)
        self.assertEqual(len(detail.data["products"]), 1)

    def test_company_scope_is_deny_by_default(self):
        hidden = Supplier.objects.create(organization=self.organization, company=self.other_company, code="hidden", name="Hidden supplier")
        visible = Supplier.objects.create(organization=self.organization, company=self.company, code="visible", name="Visible supplier")
        response = self.client.get("/api/v1/purchases/suppliers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data["results"]}
        self.assertIn(str(visible.id), ids)
        self.assertNotIn(str(hidden.id), ids)
        hidden_detail = self.client.get(f"/api/v1/purchases/suppliers/{hidden.id}/")
        self.assertEqual(hidden_detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_rejects_company_outside_granted_scope_on_create(self):
        response = self.client.post("/api/v1/purchases/suppliers/", {"company_id": str(self.other_company.id), "code": "forbidden", "name": "Forbidden"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supplier_product_rejects_other_company_specific_product(self):
        supplier = Supplier.objects.create(organization=self.organization, company=self.company, code="supplier", name="Supplier")
        other_product = Product.objects.create(organization=self.organization, company=self.other_company, code="other-product", name="Other product", product_type=Product.ProductType.FABRIC, unit=self.unit)
        response = self.client.post(f"/api/v1/purchases/suppliers/{supplier.id}/products/", {"product_id": str(other_product.id), "unit_id": str(self.unit.id), "minimum_quantity": "1.0000"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
