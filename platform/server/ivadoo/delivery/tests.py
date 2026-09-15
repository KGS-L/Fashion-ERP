from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import FashionModel, Product
from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.inventory.models import StockLocation, StockMovement, StockPosition, Warehouse
from ivadoo.inventory.services import apply_stock_movement
from ivadoo.manufacturing.models import BillOfMaterials, ManufacturingOrder
from ivadoo.manufacturing.production_models import ManufacturingOutputReceipt
from ivadoo.organizations.models import Company, Organization
from ivadoo.sales.models import Order, OrderLine

from .models import Delivery, DeliveryProof


class DeliveryApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Delivery", slug="delivery")
        self.company = Company.objects.create(organization=self.organization, name="Maison", code="delivery-maison")
        self.customer = Customer.objects.create(organization=self.organization, company=self.company, code="DEL-C1", display_name="Client")
        self.user = User.objects.create_user(username="delivery.manager", password="Strong-Test-Password-42!", organization=self.organization)
        role = Role.objects.create(organization=self.organization, code="delivery-manager", name="Delivery manager", is_active=True)
        role.permissions.set(Permission.objects.filter(code__in=("delivery.delivery.view", "delivery.delivery.manage", "delivery.delivery.transition")))
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.piece = UnitOfMeasure.objects.create(organization=self.organization, code="pc-delivery", name="Piece", symbol="pc", category="unit", ratio_to_base=Decimal("1"), rounding=Decimal("1"))
        self.finished = Product.objects.create(organization=self.organization, company=self.company, code="finished-delivery", name="Finished garment", product_type=Product.ProductType.FINISHED_GOOD, unit=self.piece)
        self.fashion_model = FashionModel.objects.create(organization=self.organization, company=self.company, code="delivery-model", name="Delivery model")
        self.order = Order.objects.create(organization=self.organization, company=self.company, customer=self.customer, number="DEL-O-1", status=Order.Status.CONFIRMED, confirmed_at=timezone.now())
        self.order_line = OrderLine.objects.create(order=self.order, fashion_model=self.fashion_model, description="Custom garment", quantity=Decimal("1"), unit_price=Decimal("50000"))
        self.warehouse = Warehouse.objects.create(organization=self.organization, company=self.company, code="del-wh", name="Delivery warehouse")
        self.location = StockLocation.objects.create(warehouse=self.warehouse, code="finished", name="Finished goods", kind=StockLocation.Kind.INTERNAL)
        self.bom = BillOfMaterials.objects.create(organization=self.organization, company=self.company, fashion_model=self.fashion_model, output_product=self.finished, code="BOM-DEL", version=1, status=BillOfMaterials.Status.ACTIVE, batch_quantity=Decimal("1"), created_by=self.user)
        self.mo = ManufacturingOrder.objects.create(organization=self.organization, company=self.company, warehouse=self.warehouse, order=self.order, order_line=self.order_line, bom=self.bom, number="MO-DEL-1", status=ManufacturingOrder.Status.DONE, planned_quantity=Decimal("1"), produced_quantity=Decimal("1"), actual_end=timezone.now(), created_by=self.user)
        movement = apply_stock_movement(
            organization=self.organization, actor=self.user, movement_type=StockMovement.MovementType.PRODUCTION_OUTPUT,
            quantity=Decimal("1"), product=self.finished, unit=self.piece, destination_location=self.location,
            reference_type="manufacturing.manufacturing_order", reference_id=self.mo.id, idempotency_key="delivery-output",
        )
        self.output = ManufacturingOutputReceipt.objects.create(
            organization=self.organization, company=self.company, manufacturing_order=self.mo,
            destination_location=self.location, product=self.finished, unit=self.piece, stock_movement=movement,
            quantity=Decimal("1"), created_by=self.user,
        )

    def _create(self, *, mode="local_delivery", quantity="1", packages=True, number=None):
        payload = {
            "order_id": str(self.order.id), "number": number or f"DEL-{mode}-1", "mode": mode,
            "courier_name": "Local courier" if mode == "local_delivery" else "",
            "courier_reference": "TR-001" if mode == "local_delivery" else "",
            "lines": [{"order_line_id": str(self.order_line.id), "quantity": quantity}],
            "packages": [{"code": "PKG-1", "description": "Garment package", "is_sealed": True}] if packages else [],
        }
        return self.client.post("/api/v1/delivery/deliveries/", payload, format="json")

    def test_local_delivery_requires_timestamped_proof_and_issues_finished_stock(self):
        created = self._create()
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        delivery_id = created.data["id"]
        self.assertEqual(self.client.post(f"/api/v1/delivery/deliveries/{delivery_id}/actions/prepare/", {}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post(f"/api/v1/delivery/deliveries/{delivery_id}/actions/assign/", {}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post(f"/api/v1/delivery/deliveries/{delivery_id}/actions/ship/", {}, format="json").status_code, status.HTTP_200_OK)
        no_proof = self.client.post(f"/api/v1/delivery/deliveries/{delivery_id}/actions/deliver/", {}, format="json")
        self.assertEqual(no_proof.status_code, status.HTTP_400_BAD_REQUEST)
        delivered = self.client.post(
            f"/api/v1/delivery/deliveries/{delivery_id}/actions/deliver/",
            {"proof": {"proof_type": "recipient_ack", "recipient_name": "Client", "evidence_reference": "proofs/del-1"}}, format="json",
        )
        self.assertEqual(delivered.status_code, status.HTTP_200_OK)
        self.assertEqual(delivered.data["status"], Delivery.Status.DELIVERED)
        proof = DeliveryProof.objects.get(delivery_id=delivery_id)
        self.assertIsNotNone(proof.recorded_at)
        position = StockPosition.objects.get(location=self.location, product=self.finished, product_variant=None, unit=self.piece)
        self.assertEqual(position.quantity_available, Decimal("0"))
        self.assertEqual(
            StockMovement.objects.filter(reference_type="delivery.delivery_line", movement_type=StockMovement.MovementType.ISSUE).count(),
            1,
        )

    def test_partial_quantity_can_be_prepared_after_issue_63(self):
        created = self._create(quantity="0.5")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        response = self.client.post(f"/api/v1/delivery/deliveries/{created.data['id']}/actions/prepare/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Delivery.Status.PREPARED)

    def test_pickup_follows_separate_transition_path(self):
        created = self._create(mode="pickup")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        delivery_id = created.data["id"]
        self.assertEqual(self.client.post(f"/api/v1/delivery/deliveries/{delivery_id}/actions/prepare/", {}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post(f"/api/v1/delivery/deliveries/{delivery_id}/actions/ready_for_pickup/", {}, format="json").status_code, status.HTTP_200_OK)
        picked = self.client.post(
            f"/api/v1/delivery/deliveries/{delivery_id}/actions/pickup/",
            {"proof": {"proof_type": "signature", "recipient_name": "Client", "evidence_reference": "proofs/pickup-1"}}, format="json",
        )
        self.assertEqual(picked.status_code, status.HTTP_200_OK)
        self.assertEqual(picked.data["status"], Delivery.Status.PICKED_UP)

    def test_preparation_requires_a_package(self):
        created = self._create(packages=False)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        response = self.client.post(f"/api/v1/delivery/deliveries/{created.data['id']}/actions/prepare/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_without_delivery_scope_sees_no_deliveries(self):
        self.assertEqual(self._create().status_code, status.HTTP_201_CREATED)
        outsider = User.objects.create_user(username="delivery.outsider", password="Strong-Test-Password-42!", organization=self.organization)
        _, token = create_api_session(user=outsider)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/v1/delivery/deliveries/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
