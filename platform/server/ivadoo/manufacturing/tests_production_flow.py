from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import FashionModel, Product
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.inventory.models import StockLot, StockMovement, StockPosition, StockReservation, Warehouse, StockLocation
from ivadoo.inventory.services import apply_stock_movement, reserve_stock
from ivadoo.organizations.models import Company, Organization

from .models import BillOfMaterials, BillOfMaterialsLine, ManufacturingOrder
from .production_models import ManufacturingMaterialConsumption, ManufacturingOutputReceipt
from .services import create_manufacturing_order, transition_manufacturing_order


class ManufacturingProductionFlowTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Production Org", slug="production-org")
        self.company = Company.objects.create(
            organization=self.organization,
            name="Production Company",
            code="production-company",
        )
        self.meter = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="m-prod",
            name="Meter",
            symbol="m",
            category="length",
            ratio_to_base=Decimal("1"),
            rounding=Decimal("0.01"),
        )
        self.piece = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="pc-prod",
            name="Piece",
            symbol="pc",
            category="count",
            ratio_to_base=Decimal("1"),
            rounding=Decimal("1"),
        )
        self.fabric = Product.objects.create(
            organization=self.organization,
            company=self.company,
            code="fabric-prod",
            name="Production fabric",
            product_type=Product.ProductType.FABRIC,
            unit=self.meter,
        )
        self.finished = Product.objects.create(
            organization=self.organization,
            company=self.company,
            code="dress-prod",
            name="Finished dress",
            product_type=Product.ProductType.FINISHED_GOOD,
            unit=self.piece,
        )
        self.fashion_model = FashionModel.objects.create(
            organization=self.organization,
            company=self.company,
            code="model-prod",
            name="Production model",
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            company=self.company,
            code="prod-main",
            name="Production warehouse",
        )
        self.raw_location = StockLocation.objects.create(
            warehouse=self.warehouse, code="raw-prod", name="Raw materials"
        )
        self.finished_location = StockLocation.objects.create(
            warehouse=self.warehouse, code="finished-prod", name="Finished goods"
        )
        self.user = User.objects.create_user(
            username="production.manager",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        role = Role.objects.create(
            organization=self.organization,
            code="production-manager",
            name="Production manager",
            is_active=True,
        )
        role.permissions.set(
            Permission.objects.filter(
                code__in=(
                    "manufacturing.order.view",
                    "manufacturing.order.manage",
                    "manufacturing.order.transition",
                    "manufacturing.material.reserve",
                    "manufacturing.material.consume",
                    "manufacturing.material.consume_supplemental",
                    "manufacturing.material.remnant",
                    "manufacturing.order.complete",
                    "inventory.stock.view",
                    "inventory.stock.manage",
                    "inventory.stock.reserve",
                )
            )
        )
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.bom = BillOfMaterials.objects.create(
            organization=self.organization,
            company=self.company,
            fashion_model=self.fashion_model,
            output_product=self.finished,
            code="BOM-PROD",
            version=1,
            status=BillOfMaterials.Status.ACTIVE,
            batch_quantity=Decimal("1"),
            created_by=self.user,
        )
        BillOfMaterialsLine.objects.create(
            bom=self.bom,
            product=self.fabric,
            quantity=Decimal("5"),
            unit=self.meter,
            position=1,
        )
        self.mo = create_manufacturing_order(
            actor=self.user,
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            bom=self.bom,
            number="MO-PROD-1",
            planned_quantity=Decimal("1"),
        )
        apply_stock_movement(
            organization=self.organization,
            actor=self.user,
            movement_type=StockMovement.MovementType.ADJUSTMENT_IN,
            quantity=Decimal("10"),
            product=self.fabric,
            unit=self.meter,
            destination_location=self.raw_location,
            idempotency_key="prod-opening-stock",
        )
        transition_manufacturing_order(
            manufacturing_order=self.mo, action="ready", actor=self.user
        )
        self.reservation = reserve_stock(
            organization=self.organization,
            actor=self.user,
            location=self.raw_location,
            product=self.fabric,
            unit=self.meter,
            quantity=Decimal("5"),
            production_order_id=self.mo.id,
            idempotency_key="prod-reservation",
        )
        transition_manufacturing_order(
            manufacturing_order=self.mo, action="start", actor=self.user
        )
        self.mo.refresh_from_db()
        self.requirement = self.mo.material_requirements.get()

    def consume(self, **overrides):
        allocation = {
            "requirement_id": str(self.requirement.id),
            "reservation_id": str(self.reservation.id),
            "quantity": "2.0000",
            "disposition": "consumed",
            "idempotency_key": "consume-1",
        }
        allocation.update(overrides)
        return self.client.post(
            f"/api/v1/manufacturing/orders/{self.mo.id}/consume-materials/",
            {"allocations": [allocation]},
            format="json",
        )

    def test_partial_reserved_consumption_is_idempotent_and_traceable(self):
        first = self.consume()
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        duplicate = self.consume()
        self.assertEqual(duplicate.status_code, status.HTTP_200_OK, duplicate.data)
        self.assertEqual(ManufacturingMaterialConsumption.objects.count(), 1)
        self.assertEqual(
            StockMovement.objects.filter(
                movement_type=StockMovement.MovementType.PRODUCTION_CONSUMPTION
            ).count(),
            1,
        )
        position = StockPosition.objects.get(
            location=self.raw_location, product=self.fabric
        )
        self.assertEqual(position.quantity_reserved, Decimal("3"))

        final = self.consume(quantity="3.0000", idempotency_key="consume-2")
        self.assertEqual(final.status_code, status.HTTP_200_OK, final.data)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, StockReservation.Status.CONSUMED)
        position.refresh_from_db()
        self.assertEqual(position.quantity_reserved, Decimal("0"))

    def test_supplemental_scrap_remnant_variance_and_single_finished_output(self):
        self.assertEqual(self.consume().status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.consume(quantity="3.0000", idempotency_key="consume-2").status_code,
            status.HTTP_200_OK,
        )
        supplemental = self.client.post(
            f"/api/v1/manufacturing/orders/{self.mo.id}/consume-materials/",
            {
                "allocations": [
                    {
                        "requirement_id": str(self.requirement.id),
                        "source_location_id": str(self.raw_location.id),
                        "quantity": "1.0000",
                        "disposition": "scrap",
                        "reason": "Cutting loss",
                        "idempotency_key": "supplemental-scrap-1",
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(supplemental.status_code, status.HTTP_200_OK, supplemental.data)

        remnant = self.client.post(
            f"/api/v1/manufacturing/orders/{self.mo.id}/remnants/",
            {
                "requirement_id": str(self.requirement.id),
                "location_id": str(self.raw_location.id),
                "quantity": "1.0000",
                "code": "REM-MO-PROD-1",
                "reason": "Reusable cutting remnant",
                "idempotency_key": "remnant-1",
            },
            format="json",
        )
        self.assertEqual(remnant.status_code, status.HTTP_201_CREATED, remnant.data)
        stock_lot = StockLot.objects.get(id=remnant.data["stock_lot_id"])
        self.assertEqual(stock_lot.kind, StockLot.Kind.REMNANT)
        self.assertEqual(stock_lot.remaining_quantity, Decimal("1"))

        variance = self.client.get(
            f"/api/v1/manufacturing/orders/{self.mo.id}/material-variance/"
        )
        self.assertEqual(variance.status_code, status.HTTP_200_OK, variance.data)
        row = variance.data[0]
        self.assertEqual(Decimal(row["planned_quantity"]), Decimal("5"))
        self.assertEqual(Decimal(row["gross_consumed_quantity"]), Decimal("6"))
        self.assertEqual(Decimal(row["scrap_quantity"]), Decimal("1"))
        self.assertEqual(Decimal(row["reusable_remnant_quantity"]), Decimal("1"))
        self.assertEqual(Decimal(row["net_consumed_quantity"]), Decimal("5"))
        self.assertEqual(Decimal(row["variance_quantity"]), Decimal("0"))

        complete_url = f"/api/v1/manufacturing/orders/{self.mo.id}/complete-production/"
        payload = {
            "produced_quantity": "1.0000",
            "destination_location_id": str(self.finished_location.id),
            "reason": "Production completed",
        }
        first = self.client.post(complete_url, payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        second = self.client.post(complete_url, payload, format="json")
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(ManufacturingOutputReceipt.objects.filter(manufacturing_order=self.mo).count(), 1)
        self.assertEqual(
            StockMovement.objects.filter(
                reference_type="manufacturing.manufacturing_order",
                reference_id=self.mo.id,
                movement_type=StockMovement.MovementType.PRODUCTION_OUTPUT,
            ).count(),
            1,
        )
        finished_position = StockPosition.objects.get(
            location=self.finished_location, product=self.finished
        )
        self.assertEqual(finished_position.quantity_available, Decimal("1"))
        self.mo.refresh_from_db()
        self.assertEqual(self.mo.status, ManufacturingOrder.Status.DONE)

    def test_completion_rolls_back_until_material_reservations_are_resolved(self):
        response = self.client.post(
            f"/api/v1/manufacturing/orders/{self.mo.id}/complete-production/",
            {
                "produced_quantity": "1.0000",
                "destination_location_id": str(self.finished_location.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.mo.refresh_from_db()
        self.assertEqual(self.mo.status, ManufacturingOrder.Status.IN_PROGRESS)
        self.assertFalse(
            StockMovement.objects.filter(
                reference_type="manufacturing.manufacturing_order",
                reference_id=self.mo.id,
            ).exists()
        )

    def test_direct_done_action_is_not_available_after_stock_coupled_completion(self):
        response = self.client.post(
            f"/api/v1/manufacturing/orders/{self.mo.id}/actions/",
            {"action": "done", "produced_quantity": "1.0000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
