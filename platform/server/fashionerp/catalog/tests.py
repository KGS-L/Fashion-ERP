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


    def test_create_season_collection_and_fashion_model(self):
        season = self.client.post("/api/v1/products/seasons/", {
            "code": "ss27", "name": "Spring Summer 2027", "year": 2027,
            "start_date": "2027-01-01", "end_date": "2027-06-30",
        }, format="json")
        self.assertEqual(season.status_code, status.HTTP_201_CREATED)

        collection = self.client.post("/api/v1/products/collections/", {
            "company_id": str(self.company.id), "season_id": season.data["id"],
            "code": "heritage-27", "name": "Heritage 27",
            "media_references": [{"kind": "lookbook", "ref": "media://heritage-cover"}],
        }, format="json")
        self.assertEqual(collection.status_code, status.HTTP_201_CREATED)

        model = self.client.post("/api/v1/products/fashion-models/", {
            "company_id": str(self.company.id), "collection_id": collection.data["id"],
            "code": "robe-aya", "name": "Robe Aya",
            "instructions": "Preserve the asymmetric neckline.",
            "media_references": [{"kind": "sketch", "ref": "media://robe-aya-sketch"}],
            "variants": [
                {"code": "aya-indigo-m", "color": "Indigo", "size": "M"},
                {"code": "aya-gold-l", "color": "Gold", "size": "L"},
            ],
        }, format="json")
        self.assertEqual(model.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(model.data["variants"]), 2)

    def test_rejects_invalid_season_date_range(self):
        response = self.client.post("/api/v1/products/seasons/", {
            "code": "invalid", "name": "Invalid", "start_date": "2027-06-30", "end_date": "2027-01-01",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_model_material_requirement_is_reference_data_not_inventory(self):
        fabric = self.client.post("/api/v1/products/", {
            "company_id": str(self.company.id), "code": "linen", "name": "Linen",
            "product_type": "fabric", "unit_id": str(self.meter.id),
        }, format="json")
        model = self.client.post("/api/v1/products/fashion-models/", {
            "company_id": str(self.company.id), "code": "shirt-ref", "name": "Reference Shirt",
            "variants": [{"code": "shirt-m", "size": "M"}],
        }, format="json")
        response = self.client.post(
            f"/api/v1/products/fashion-models/{model.data['id']}/material-requirements/",
            {
                "model_variant_id": model.data["variants"][0]["id"],
                "product_id": fabric.data["id"], "quantity": "2.2500",
                "unit_id": str(self.meter.id), "waste_rate": "0.0500",
                "notes": "Reference consumption before cutting.",
            }, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data["quantity"]), Decimal("2.2500"))

    def test_model_material_requirement_rejects_non_positive_quantity(self):
        fabric = self.client.post("/api/v1/products/", {
            "company_id": str(self.company.id), "code": "cotton-zero", "name": "Cotton",
            "product_type": "fabric", "unit_id": str(self.meter.id),
        }, format="json")
        model = self.client.post("/api/v1/products/fashion-models/", {
            "company_id": str(self.company.id), "code": "model-zero", "name": "Model Zero",
        }, format="json")
        response = self.client.post(
            f"/api/v1/products/fashion-models/{model.data['id']}/material-requirements/",
            {"product_id": fabric.data["id"], "quantity": "0", "unit_id": str(self.meter.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_catalog_is_deny_by_default_without_view_grant(self):
        outsider = User.objects.create_user(username="catalog.no-grant", password="Strong-Test-Password-42!", organization=self.organization)
        _, token = create_api_session(user=outsider)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        Product.objects.create(organization=self.organization, company=None, code="shared-hidden", name="Shared Hidden", product_type="service", unit=self.meter)
        response = self.client.get("/api/v1/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
