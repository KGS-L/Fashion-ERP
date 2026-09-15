import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase

from ivadoo.catalog.models import FashionModel, Product
from ivadoo.identity.models import User
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.inventory.models import StockMovement, StockPosition, StockReservation, Warehouse, StockLocation
from ivadoo.inventory.services import apply_stock_movement, reserve_stock
from ivadoo.organizations.models import Company, Organization

from .models import BillOfMaterials, BillOfMaterialsLine, ManufacturingOrder
from .production_models import ManufacturingMaterialConsumption
from .production_services import consume_manufacturing_materials
from .services import create_manufacturing_order, transition_manufacturing_order


class ManufacturingProductionConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.organization = Organization.objects.create(
            name="Production Concurrency Org",
            slug="production-concurrency-org",
        )
        self.company = Company.objects.create(
            organization=self.organization,
            name="Production Concurrency Company",
            code="production-concurrency-company",
        )
        self.meter = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="m-prod-concurrency",
            name="Meter",
            symbol="m",
            category="length",
            ratio_to_base=Decimal("1"),
            rounding=Decimal("0.01"),
        )
        self.fabric = Product.objects.create(
            organization=self.organization,
            company=self.company,
            code="fabric-prod-concurrency",
            name="Production concurrency fabric",
            product_type=Product.ProductType.FABRIC,
            unit=self.meter,
        )
        self.fashion_model = FashionModel.objects.create(
            organization=self.organization,
            company=self.company,
            code="model-prod-concurrency",
            name="Production concurrency model",
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            company=self.company,
            code="prod-concurrency-main",
            name="Production concurrency warehouse",
        )
        self.raw_location = StockLocation.objects.create(
            warehouse=self.warehouse,
            code="raw-prod-concurrency",
            name="Raw materials",
        )
        self.user = User.objects.create_user(
            username="production.concurrency",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        self.bom = BillOfMaterials.objects.create(
            organization=self.organization,
            company=self.company,
            fashion_model=self.fashion_model,
            code="BOM-PROD-CONCURRENCY",
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
        self.manufacturing_order = create_manufacturing_order(
            actor=self.user,
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            bom=self.bom,
            number="MO-PROD-CONCURRENCY-1",
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
            idempotency_key="prod-concurrency-opening-stock",
        )
        transition_manufacturing_order(
            manufacturing_order=self.manufacturing_order,
            action="ready",
            actor=self.user,
        )
        self.reservation = reserve_stock(
            organization=self.organization,
            actor=self.user,
            location=self.raw_location,
            product=self.fabric,
            unit=self.meter,
            quantity=Decimal("5"),
            production_order_id=self.manufacturing_order.id,
            idempotency_key="prod-concurrency-reservation",
        )
        transition_manufacturing_order(
            manufacturing_order=self.manufacturing_order,
            action="start",
            actor=self.user,
        )
        self.requirement = self.manufacturing_order.material_requirements.get()

    def _consume_three(self, barrier, idempotency_key):
        close_old_connections()
        try:
            actor = User.objects.get(pk=self.user.pk)
            manufacturing_order = ManufacturingOrder.objects.get(
                pk=self.manufacturing_order.pk
            )
            reservation = StockReservation.objects.get(pk=self.reservation.pk)
            barrier.wait(timeout=10)
            try:
                consumptions = consume_manufacturing_materials(
                    manufacturing_order=manufacturing_order,
                    allocations=[
                        {
                            "requirement_id": self.requirement.id,
                            "reservation": reservation,
                            "quantity": Decimal("3"),
                            "disposition": ManufacturingMaterialConsumption.Disposition.CONSUMED,
                            "reason": "Concurrent production consumption",
                            "idempotency_key": idempotency_key,
                        }
                    ],
                    actor=actor,
                )
            except ValidationError:
                return "rejected"
            return str(consumptions[0].id)
        finally:
            close_old_connections()

    def test_concurrent_consumptions_cannot_overconsume_one_reservation(self):
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(self._consume_three, barrier, "concurrent-consume-a"),
                executor.submit(self._consume_three, barrier, "concurrent-consume-b"),
            ]
            results = [future.result(timeout=20) for future in futures]

        self.assertEqual(results.count("rejected"), 1)
        self.assertEqual(
            ManufacturingMaterialConsumption.objects.filter(
                manufacturing_order=self.manufacturing_order
            ).count(),
            1,
        )
        self.assertEqual(
            StockMovement.objects.filter(
                movement_type=StockMovement.MovementType.PRODUCTION_CONSUMPTION,
                reference_type="inventory.stock_reservation",
                reference_id=self.reservation.id,
            ).count(),
            1,
        )
        position = StockPosition.objects.get(
            location=self.raw_location,
            product=self.fabric,
        )
        self.assertEqual(position.quantity_reserved, Decimal("2"))
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, StockReservation.Status.ACTIVE)
