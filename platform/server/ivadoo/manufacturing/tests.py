from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import FashionModel, Product
from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.inventory.models import StockLocation, StockMovement, StockPosition, StockReservation, Warehouse
from ivadoo.organizations.models import Company, Organization
from ivadoo.sales.models import Order, OrderLine

from .models import BillOfMaterials, ManufacturingMaterialRequirement, ManufacturingOrder


class ManufacturingApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Manufacturing Org", slug="manufacturing-org")
        self.company = Company.objects.create(
            organization=self.organization,
            name="Manufacturing Company",
            code="manufacturing-company",
        )
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="m",
            name="Meter",
            symbol="m",
            category="length",
            ratio_to_base=Decimal("1"),
            rounding=Decimal("0.01"),
        )
        self.fabric = Product.objects.create(
            organization=self.organization,
            company=self.company,
            code="fabric-mfg",
            name="Manufacturing fabric",
            product_type=Product.ProductType.FABRIC,
            unit=self.unit,
        )
        self.fashion_model = FashionModel.objects.create(
            organization=self.organization,
            company=self.company,
            code="dress-mfg",
            name="Manufacturing dress",
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            company=self.company,
            code="mfg-main",
            name="Manufacturing warehouse",
        )
        self.location = StockLocation.objects.create(
            warehouse=self.warehouse,
            code="raw",
            name="Raw materials",
        )
        StockPosition.objects.create(
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            location=self.location,
            product=self.fabric,
            unit=self.unit,
            quantity_available=Decimal("50"),
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="customer-mfg",
            display_name="Manufacturing customer",
        )
        self.order = Order.objects.create(
            organization=self.organization,
            company=self.company,
            customer=self.customer,
            number="SO-MFG-1",
            status=Order.Status.CONFIRMED,
        )
        self.order_line = OrderLine.objects.create(
            order=self.order,
            fashion_model=self.fashion_model,
            description="Made-to-order dress",
            quantity=Decimal("2"),
            unit_price=Decimal("15000"),
        )
        self.user = User.objects.create_user(
            username="manufacturing.manager",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        permission_codes = (
            "manufacturing.bom.view",
            "manufacturing.bom.manage",
            "manufacturing.order.view",
            "manufacturing.order.manage",
            "manufacturing.order.transition",
            "manufacturing.material.reserve",
            "inventory.stock.manage",
            "inventory.stock.view",
        )
        role = Role.objects.create(
            organization=self.organization,
            code="manufacturing-manager",
            name="Manufacturing manager",
            is_active=True,
        )
        role.permissions.set(Permission.objects.filter(code__in=permission_codes))
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def create_active_bom(self):
        response = self.client.post(
            "/api/v1/manufacturing/boms/",
            {
                "company_id": str(self.company.id),
                "fashion_model_id": str(self.fashion_model.id),
                "code": "BOM-DRESS",
                "version": 1,
                "batch_quantity": "1.0000",
                "lines": [
                    {
                        "product_id": str(self.fabric.id),
                        "unit_id": str(self.unit.id),
                        "quantity": "2.0000",
                        "waste_rate": "0.1000",
                        "position": 1,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        bom_id = response.data["id"]
        activated = self.client.post(
            f"/api/v1/manufacturing/boms/{bom_id}/actions/",
            {"action": "activate"},
            format="json",
        )
        self.assertEqual(activated.status_code, status.HTTP_200_OK, activated.data)
        self.assertEqual(activated.data["status"], BillOfMaterials.Status.ACTIVE)
        return activated.data

    def test_order_creation_snapshots_bom_requirements_without_consuming_stock(self):
        bom = self.create_active_bom()
        response = self.client.post(
            "/api/v1/manufacturing/orders/",
            {
                "company_id": str(self.company.id),
                "warehouse_id": str(self.warehouse.id),
                "order_id": str(self.order.id),
                "order_line_id": str(self.order_line.id),
                "bom_id": bom["id"],
                "number": "MO-1",
                "planned_quantity": "2.0000",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["status"], ManufacturingOrder.Status.DRAFT)
        self.assertEqual(len(response.data["material_requirements"]), 1)
        requirement = ManufacturingMaterialRequirement.objects.get(
            manufacturing_order_id=response.data["id"]
        )
        self.assertEqual(requirement.planned_quantity, Decimal("4.4000"))
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(StockReservation.objects.count(), 0)

    def test_ready_order_can_reserve_calculated_material_without_consuming_it(self):
        bom = self.create_active_bom()
        created = self.client.post(
            "/api/v1/manufacturing/orders/",
            {
                "company_id": str(self.company.id),
                "warehouse_id": str(self.warehouse.id),
                "order_id": str(self.order.id),
                "order_line_id": str(self.order_line.id),
                "bom_id": bom["id"],
                "number": "MO-RESERVE",
                "planned_quantity": "2.0000",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        mo_id = created.data["id"]
        ready = self.client.post(
            f"/api/v1/manufacturing/orders/{mo_id}/actions/",
            {"action": "ready"},
            format="json",
        )
        self.assertEqual(ready.status_code, status.HTTP_200_OK, ready.data)
        requirement_id = created.data["material_requirements"][0]["id"]
        reserve = self.client.post(
            f"/api/v1/manufacturing/orders/{mo_id}/reserve-materials/",
            {
                "allocations": [
                    {
                        "requirement_id": requirement_id,
                        "location_id": str(self.location.id),
                        "quantity": "4.4000",
                        "idempotency_key": "mo-reserve-materials-1",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(reserve.status_code, status.HTTP_200_OK, reserve.data)
        reservation = StockReservation.objects.get(production_order_id=mo_id)
        self.assertEqual(reservation.quantity, Decimal("4.4000"))
        self.assertEqual(StockMovement.objects.count(), 0)
        position = StockPosition.objects.get(location=self.location, product=self.fabric)
        self.assertEqual(position.quantity_available, Decimal("45.6000"))
        self.assertEqual(position.quantity_reserved, Decimal("4.4000"))

    def test_active_bom_is_immutable_and_status_cannot_be_patched_directly(self):
        bom = self.create_active_bom()
        patch = self.client.patch(
            f"/api/v1/manufacturing/boms/{bom['id']}/",
            {"notes": "must create a new version"},
            format="json",
        )
        self.assertEqual(patch.status_code, status.HTTP_400_BAD_REQUEST)
        instance = BillOfMaterials.objects.get(id=bom["id"])
        self.assertEqual(instance.status, BillOfMaterials.Status.ACTIVE)
