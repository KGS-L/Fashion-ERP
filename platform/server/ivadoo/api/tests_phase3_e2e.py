from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import FashionModel, Product
from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import Currency, UnitOfMeasure
from ivadoo.inventory.models import StockLocation, StockPosition, Warehouse
from ivadoo.manufacturing.models import BillOfMaterials, BillOfMaterialsLine
from ivadoo.manufacturing.production_models import ManufacturingOutputReceipt
from ivadoo.manufacturing.services import (
    create_manufacturing_order,
    reserve_manufacturing_materials,
    transition_manufacturing_order,
)
from ivadoo.organizations.models import Company, Organization
from ivadoo.purchases.models import PurchaseOrder, PurchaseOrderLine, Supplier
from ivadoo.quality.models import QualityInspection, QualityRework
from ivadoo.sales.models import Order, OrderLine


class Phase3OperationalJourneyTests(APITestCase):
    """Pilot journey covering procurement, stock, production, quality and delivery."""

    def setUp(self):
        self.organization = Organization.objects.create(name="Phase 3 E2E", slug="phase-3-e2e")
        self.company = Company.objects.create(
            organization=self.organization,
            name="Maison Phase 3",
            code="phase-3-company",
        )
        self.user = User.objects.create_user(
            username="phase3.operator",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        role = Role.objects.create(
            organization=self.organization,
            code="phase3-operator",
            name="Phase 3 operator",
            is_active=True,
        )
        role.permissions.set(
            Permission.objects.filter(
                code__in=(
                    "inventory.stock.view",
                    "inventory.stock.manage",
                    "inventory.stock.reserve",
                    "purchase.receipt.view",
                    "purchase.receipt.manage",
                    "purchase.receipt.control",
                    "purchase.receipt.post",
                    "manufacturing.order.view",
                    "manufacturing.order.manage",
                    "manufacturing.order.transition",
                    "manufacturing.material.reserve",
                    "manufacturing.material.consume",
                    "manufacturing.order.complete",
                    "quality.inspection.view",
                    "quality.inspection.manage",
                    "quality.inspection.complete",
                    "quality.rework.manage",
                    "delivery.delivery.view",
                    "delivery.delivery.manage",
                    "delivery.delivery.transition",
                )
            )
        )
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.currency = Currency.objects.create(
            code="XOF",
            name="West African CFA franc",
            symbol="FCFA",
            decimal_places=0,
            rounding=Decimal("1"),
        )
        self.meter = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="m-e2e",
            name="Meter",
            symbol="m",
            category="length",
            ratio_to_base=Decimal("1"),
            rounding=Decimal("0.01"),
        )
        self.piece = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="pc-e2e",
            name="Piece",
            symbol="pc",
            category="unit",
            ratio_to_base=Decimal("1"),
            rounding=Decimal("1"),
        )
        self.fabric = Product.objects.create(
            organization=self.organization,
            company=self.company,
            code="fabric-e2e",
            name="Pilot fabric",
            product_type=Product.ProductType.FABRIC,
            unit=self.meter,
        )
        self.finished = Product.objects.create(
            organization=self.organization,
            company=self.company,
            code="finished-e2e",
            name="Pilot garment",
            product_type=Product.ProductType.FINISHED_GOOD,
            unit=self.piece,
        )
        self.model = FashionModel.objects.create(
            organization=self.organization,
            company=self.company,
            code="model-e2e",
            name="Pilot model",
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="customer-e2e",
            display_name="Pilot customer",
        )
        self.order = Order.objects.create(
            organization=self.organization,
            company=self.company,
            customer=self.customer,
            number="SO-E2E-1",
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        self.order_line = OrderLine.objects.create(
            order=self.order,
            fashion_model=self.model,
            description="Two pilot garments",
            quantity=Decimal("2"),
            unit_price=Decimal("50000"),
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            company=self.company,
            code="e2e-wh",
            name="Pilot warehouse",
        )
        self.receiving = StockLocation.objects.create(
            warehouse=self.warehouse,
            code="receiving-e2e",
            name="Receiving",
            kind=StockLocation.Kind.RECEIVING,
        )
        self.finished_location = StockLocation.objects.create(
            warehouse=self.warehouse,
            code="finished-e2e",
            name="Finished goods",
            kind=StockLocation.Kind.INTERNAL,
        )
        self.supplier = Supplier.objects.create(
            organization=self.organization,
            company=self.company,
            code="supplier-e2e",
            name="Pilot supplier",
            currency=self.currency,
        )
        self.purchase_order = PurchaseOrder.objects.create(
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            supplier=self.supplier,
            currency=self.currency,
            number="PO-E2E-1",
            status=PurchaseOrder.Status.ORDERED,
            ordered_at=timezone.now(),
            created_by=self.user,
        )
        self.purchase_line = PurchaseOrderLine.objects.create(
            purchase_order=self.purchase_order,
            product=self.fabric,
            unit=self.meter,
            quantity=Decimal("5"),
            unit_price=Decimal("2500"),
        )

    def test_order_to_partial_delivery_with_procurement_and_quality_rework(self):
        receipt = self.client.post(
            "/api/v1/purchases/receipts/",
            {
                "purchase_order_id": str(self.purchase_order.id),
                "warehouse_id": str(self.warehouse.id),
                "number": "RCPT-E2E-1",
                "lines": [
                    {
                        "purchase_order_line_id": str(self.purchase_line.id),
                        "location_id": str(self.receiving.id),
                        "received_quantity": "5.0000",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(receipt.status_code, status.HTTP_201_CREATED, receipt.data)
        receipt_line_id = receipt.data["lines"][0]["id"]

        incoming_inspection = self.client.post(
            "/api/v1/quality/inspections/",
            {
                "company_id": str(self.company.id),
                "inspection_type": "receiving",
                "purchase_receipt_line_id": receipt_line_id,
                "blocking": True,
                "criteria": [{"code": "fabric", "label": "Fabric quality", "result": "pass"}],
                "defects": [],
            },
            format="json",
        )
        self.assertEqual(incoming_inspection.status_code, status.HTTP_201_CREATED, incoming_inspection.data)
        accepted_incoming = self.client.post(
            f"/api/v1/quality/inspections/{incoming_inspection.data['id']}/complete/",
            {"decision": "accept"},
            format="json",
        )
        self.assertEqual(accepted_incoming.status_code, status.HTTP_200_OK, accepted_incoming.data)

        controlled = self.client.post(
            f"/api/v1/purchases/receipts/{receipt.data['id']}/actions/",
            {
                "action": "control",
                "lines": [
                    {
                        "line_id": receipt_line_id,
                        "accepted_quantity": "5.0000",
                        "rejected_quantity": "0.0000",
                        "note": "Incoming quality accepted",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(controlled.status_code, status.HTTP_200_OK, controlled.data)
        posted = self.client.post(
            f"/api/v1/purchases/receipts/{receipt.data['id']}/actions/",
            {"action": "post"},
            format="json",
        )
        self.assertEqual(posted.status_code, status.HTTP_200_OK, posted.data)
        raw_position = StockPosition.objects.get(location=self.receiving, product=self.fabric, unit=self.meter)
        self.assertEqual(raw_position.quantity_available, Decimal("5"))

        bom = BillOfMaterials.objects.create(
            organization=self.organization,
            company=self.company,
            fashion_model=self.model,
            output_product=self.finished,
            code="BOM-E2E",
            version=1,
            status=BillOfMaterials.Status.ACTIVE,
            batch_quantity=Decimal("1"),
            created_by=self.user,
        )
        BillOfMaterialsLine.objects.create(
            bom=bom,
            product=self.fabric,
            quantity=Decimal("2"),
            unit=self.meter,
            position=1,
        )
        manufacturing_order = create_manufacturing_order(
            actor=self.user,
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            order=self.order,
            order_line=self.order_line,
            bom=bom,
            number="MO-E2E-1",
            planned_quantity=Decimal("2"),
        )
        transition_manufacturing_order(manufacturing_order=manufacturing_order, action="ready", actor=self.user)
        requirement = manufacturing_order.material_requirements.get()
        reservation = reserve_manufacturing_materials(
            manufacturing_order=manufacturing_order,
            allocations=[
                {
                    "requirement_id": requirement.id,
                    "location": self.receiving,
                    "quantity": Decimal("4"),
                    "idempotency_key": "e2e-material-reservation",
                }
            ],
            actor=self.user,
        )[0]
        transition_manufacturing_order(manufacturing_order=manufacturing_order, action="start", actor=self.user)

        consumed = self.client.post(
            f"/api/v1/manufacturing/orders/{manufacturing_order.id}/consume-materials/",
            {
                "allocations": [
                    {
                        "requirement_id": str(requirement.id),
                        "reservation_id": str(reservation.id),
                        "quantity": "4.0000",
                        "disposition": "consumed",
                        "idempotency_key": "e2e-consumption",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(consumed.status_code, status.HTTP_200_OK, consumed.data)
        completed = self.client.post(
            f"/api/v1/manufacturing/orders/{manufacturing_order.id}/complete-production/",
            {
                "produced_quantity": "2.0000",
                "destination_location_id": str(self.finished_location.id),
                "reason": "Pilot production completed",
            },
            format="json",
        )
        self.assertEqual(completed.status_code, status.HTTP_200_OK, completed.data)
        output = ManufacturingOutputReceipt.objects.get(manufacturing_order=manufacturing_order)

        final_failed = self.client.post(
            "/api/v1/quality/inspections/",
            {
                "company_id": str(self.company.id),
                "inspection_type": "final",
                "output_receipt_id": str(output.id),
                "blocking": True,
                "criteria": [{"code": "finish", "label": "Finish", "result": "fail"}],
                "defects": [{"code": "FINISH-1", "severity": "major", "description": "Loose finishing", "quantity": "1"}],
            },
            format="json",
        )
        self.assertEqual(final_failed.status_code, status.HTTP_201_CREATED, final_failed.data)
        rework_decision = self.client.post(
            f"/api/v1/quality/inspections/{final_failed.data['id']}/complete/",
            {"decision": "rework", "reason": "Finishing defect", "rework_instructions": "Correct finishing"},
            format="json",
        )
        self.assertEqual(rework_decision.status_code, status.HTTP_200_OK, rework_decision.data)
        rework = QualityRework.objects.get(inspection_id=final_failed.data["id"])
        self.assertEqual(
            self.client.post(
                f"/api/v1/quality/reworks/{rework.id}/complete/",
                {"result_notes": "Finishing corrected"},
                format="json",
            ).status_code,
            status.HTTP_200_OK,
        )
        reinspection = self.client.post(
            "/api/v1/quality/inspections/",
            {
                "company_id": str(self.company.id),
                "inspection_type": "final",
                "output_receipt_id": str(output.id),
                "parent_inspection_id": final_failed.data["id"],
                "blocking": True,
                "criteria": [{"code": "finish", "label": "Finish", "result": "pass"}],
                "defects": [],
            },
            format="json",
        )
        self.assertEqual(reinspection.status_code, status.HTTP_201_CREATED, reinspection.data)
        accepted_final = self.client.post(
            f"/api/v1/quality/inspections/{reinspection.data['id']}/complete/",
            {"decision": "accept"},
            format="json",
        )
        self.assertEqual(accepted_final.status_code, status.HTTP_200_OK, accepted_final.data)

        delivery = self.client.post(
            "/api/v1/delivery/deliveries/",
            {
                "order_id": str(self.order.id),
                "number": "DEL-E2E-1",
                "mode": "local_delivery",
                "courier_name": "Pilot courier",
                "courier_reference": "E2E-TRIP-1",
                "lines": [{"order_line_id": str(self.order_line.id), "quantity": "1.0000"}],
                "packages": [{"code": "PKG-E2E-1", "description": "First partial delivery", "is_sealed": True}],
            },
            format="json",
        )
        self.assertEqual(delivery.status_code, status.HTTP_201_CREATED, delivery.data)
        delivery_id = delivery.data["id"]
        for action in ("prepare", "assign", "ship"):
            response = self.client.post(f"/api/v1/delivery/deliveries/{delivery_id}/actions/{action}/", {}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        delivered = self.client.post(
            f"/api/v1/delivery/deliveries/{delivery_id}/actions/deliver/",
            {"proof": {"proof_type": "recipient_ack", "recipient_name": "Pilot customer", "evidence_reference": "proofs/e2e-1"}},
            format="json",
        )
        self.assertEqual(delivered.status_code, status.HTTP_200_OK, delivered.data)
        balance = self.client.get(f"/api/v1/delivery/orders/{self.order.id}/balance/")
        self.assertEqual(balance.status_code, status.HTTP_200_OK, balance.data)
        self.assertEqual(Decimal(balance.data["lines"][0]["delivered_quantity"]), Decimal("1"))
        self.assertEqual(Decimal(balance.data["lines"][0]["remaining_to_allocate"]), Decimal("1"))
        finished_position = StockPosition.objects.get(location=self.finished_location, product=self.finished, unit=self.piece)
        self.assertEqual(finished_position.quantity_available, Decimal("1"))
        self.assertTrue(QualityInspection.objects.filter(output_receipt=output, decision=QualityInspection.Decision.ACCEPT).exists())
