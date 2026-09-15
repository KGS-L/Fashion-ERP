from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone

from ivadoo.catalog.models import FashionModel, Product
from ivadoo.customers.models import Customer
from ivadoo.delivery.models import DeliveryProof, DeliveryReturn, DeliveryReturnLine
from ivadoo.delivery.services import create_delivery, create_delivery_return, transition_delivery
from ivadoo.identity.models import User
from ivadoo.internationalization.models import Currency, UnitOfMeasure
from ivadoo.inventory.models import StockLocation, StockMovement, StockPosition, StockReservation, Warehouse
from ivadoo.inventory.services import apply_stock_movement, reserve_stock
from ivadoo.manufacturing.models import BillOfMaterials, BillOfMaterialsLine
from ivadoo.manufacturing.production_models import ManufacturingMaterialConsumption, ManufacturingOutputReceipt
from ivadoo.manufacturing.production_services import consume_manufacturing_materials
from ivadoo.manufacturing.services import create_manufacturing_order, transition_manufacturing_order
from ivadoo.organizations.models import Company, Organization
from ivadoo.purchases.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReceipt,
    PurchaseReceiptLine,
    Supplier,
    SupplierPurchaseHistory,
)
from ivadoo.purchases.receipt_services import post_receipt
from ivadoo.sales.models import Order, OrderLine


class Phase3ConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.organization = Organization.objects.create(name="Phase 3 concurrency", slug="phase3-concurrency")
        self.company = Company.objects.create(
            organization=self.organization,
            name="Maison Concurrency",
            code="phase3-concurrency-company",
        )
        self.user = User.objects.create_user(
            username="phase3.concurrent",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        self.currency = Currency.objects.create(
            code="XOF",
            name="West African CFA franc",
            symbol="FCFA",
            decimal_places=0,
            rounding=Decimal("1"),
        )
        self.meter = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="m-concurrency",
            name="Meter",
            symbol="m",
            category="length",
            ratio_to_base=Decimal("1"),
            rounding=Decimal("0.01"),
        )
        self.piece = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="pc-concurrency",
            name="Piece",
            symbol="pc",
            category="unit",
            ratio_to_base=Decimal("1"),
            rounding=Decimal("1"),
        )
        self.fabric = Product.objects.create(
            organization=self.organization,
            company=self.company,
            code="fabric-concurrency",
            name="Concurrency fabric",
            product_type=Product.ProductType.FABRIC,
            unit=self.meter,
        )
        self.finished = Product.objects.create(
            organization=self.organization,
            company=self.company,
            code="finished-concurrency",
            name="Concurrency garment",
            product_type=Product.ProductType.FINISHED_GOOD,
            unit=self.piece,
        )
        self.model = FashionModel.objects.create(
            organization=self.organization,
            company=self.company,
            code="model-concurrency",
            name="Concurrency model",
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="customer-concurrency",
            display_name="Concurrency customer",
        )
        self.order = Order.objects.create(
            organization=self.organization,
            company=self.company,
            customer=self.customer,
            number="SO-CONCURRENCY-1",
            status=Order.Status.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        self.order_line = OrderLine.objects.create(
            order=self.order,
            fashion_model=self.model,
            description="Concurrency garment",
            quantity=Decimal("1"),
            unit_price=Decimal("50000"),
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            company=self.company,
            code="concurrency-wh",
            name="Concurrency warehouse",
        )
        self.source = StockLocation.objects.create(
            warehouse=self.warehouse,
            code="source-concurrency",
            name="Source",
            kind=StockLocation.Kind.INTERNAL,
        )
        self.destination = StockLocation.objects.create(
            warehouse=self.warehouse,
            code="destination-concurrency",
            name="Destination",
            kind=StockLocation.Kind.INTERNAL,
        )
        self.receiving = StockLocation.objects.create(
            warehouse=self.warehouse,
            code="receiving-concurrency",
            name="Receiving",
            kind=StockLocation.Kind.RECEIVING,
        )

    def _run_concurrently(self, function, workers=2):
        barrier = Barrier(workers)

        def runner(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return ("ok", function(index))
            except Exception as exc:  # captured for deterministic assertions in the main test thread
                return ("error", exc)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            return list(executor.map(runner, range(workers)))

    def _seed_stock(self, *, location, product, unit, quantity, key):
        return apply_stock_movement(
            organization=self.organization,
            actor=self.user,
            movement_type=StockMovement.MovementType.ADJUSTMENT_IN,
            quantity=Decimal(quantity),
            product=product,
            unit=unit,
            destination_location=location,
            idempotency_key=key,
        )

    def test_concurrent_reservations_cannot_overbook_stock(self):
        self._seed_stock(location=self.source, product=self.fabric, unit=self.meter, quantity="5", key="reservation-opening")

        results = self._run_concurrently(
            lambda index: reserve_stock(
                organization=self.organization,
                actor=self.user,
                location=self.source,
                product=self.fabric,
                unit=self.meter,
                quantity=Decimal("4"),
                order=self.order,
                idempotency_key=f"reservation-race-{index}",
            )
        )

        self.assertEqual(sum(result[0] == "ok" for result in results), 1)
        errors = [result[1] for result in results if result[0] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValidationError)
        position = StockPosition.objects.get(location=self.source, product=self.fabric, unit=self.meter)
        self.assertEqual(position.quantity_available, Decimal("1"))
        self.assertEqual(position.quantity_reserved, Decimal("4"))
        self.assertEqual(StockReservation.objects.filter(order=self.order).count(), 1)

    def test_concurrent_transfers_serialize_and_failed_transfer_rolls_back(self):
        self._seed_stock(location=self.source, product=self.fabric, unit=self.meter, quantity="5", key="transfer-opening")

        results = self._run_concurrently(
            lambda index: apply_stock_movement(
                organization=self.organization,
                actor=self.user,
                movement_type=StockMovement.MovementType.TRANSFER,
                quantity=Decimal("4"),
                product=self.fabric,
                unit=self.meter,
                source_location=self.source,
                destination_location=self.destination,
                idempotency_key=f"transfer-race-{index}",
            )
        )

        self.assertEqual(sum(result[0] == "ok" for result in results), 1)
        self.assertEqual(sum(result[0] == "error" for result in results), 1)
        source_position = StockPosition.objects.get(location=self.source, product=self.fabric, unit=self.meter)
        destination_position = StockPosition.objects.get(location=self.destination, product=self.fabric, unit=self.meter)
        self.assertEqual(source_position.quantity_available, Decimal("1"))
        self.assertEqual(destination_position.quantity_available, Decimal("4"))

        empty_destination = StockLocation.objects.create(
            warehouse=self.warehouse,
            code="rollback-target",
            name="Rollback target",
            kind=StockLocation.Kind.INTERNAL,
        )
        with self.assertRaises(ValidationError):
            apply_stock_movement(
                organization=self.organization,
                actor=self.user,
                movement_type=StockMovement.MovementType.TRANSFER,
                quantity=Decimal("2"),
                product=self.fabric,
                unit=self.meter,
                source_location=self.source,
                destination_location=empty_destination,
                idempotency_key="rollback-transfer",
            )
        source_position.refresh_from_db()
        self.assertEqual(source_position.quantity_available, Decimal("1"))
        self.assertFalse(StockPosition.objects.filter(location=empty_destination, product=self.fabric, unit=self.meter).exists())

    def test_concurrent_receipt_posting_is_single_application(self):
        supplier = Supplier.objects.create(
            organization=self.organization,
            company=self.company,
            code="supplier-concurrency",
            name="Concurrency supplier",
            currency=self.currency,
        )
        purchase_order = PurchaseOrder.objects.create(
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            supplier=supplier,
            currency=self.currency,
            number="PO-CONCURRENCY-1",
            status=PurchaseOrder.Status.ORDERED,
            ordered_at=timezone.now(),
            created_by=self.user,
        )
        purchase_line = PurchaseOrderLine.objects.create(
            purchase_order=purchase_order,
            product=self.fabric,
            unit=self.meter,
            quantity=Decimal("5"),
            unit_price=Decimal("2500"),
        )
        receipt = PurchaseReceipt.objects.create(
            organization=self.organization,
            company=self.company,
            purchase_order=purchase_order,
            warehouse=self.warehouse,
            number="RCPT-CONCURRENCY-1",
            status=PurchaseReceipt.Status.CONTROLLED,
            controlled_by=self.user,
            controlled_at=timezone.now(),
            created_by=self.user,
        )
        PurchaseReceiptLine.objects.create(
            receipt=receipt,
            purchase_order_line=purchase_line,
            location=self.receiving,
            received_quantity=Decimal("5"),
            accepted_quantity=Decimal("5"),
            rejected_quantity=Decimal("0"),
            quality_status=PurchaseReceiptLine.QualityStatus.ACCEPTED,
        )

        results = self._run_concurrently(
            lambda _index: post_receipt(receipt=receipt, actor=self.user)
        )
        self.assertEqual(sum(result[0] == "ok" for result in results), 2)
        self.assertEqual(StockMovement.objects.filter(reference_type="purchases.receipt_line").count(), 1)
        self.assertEqual(SupplierPurchaseHistory.objects.filter(receipt_line__receipt=receipt).count(), 1)
        purchase_line.refresh_from_db()
        self.assertEqual(purchase_line.received_quantity, Decimal("5"))
        position = StockPosition.objects.get(location=self.receiving, product=self.fabric, unit=self.meter)
        self.assertEqual(position.quantity_available, Decimal("5"))

    def test_concurrent_manufacturing_consumption_is_idempotent(self):
        bom = BillOfMaterials.objects.create(
            organization=self.organization,
            company=self.company,
            fashion_model=self.model,
            output_product=self.finished,
            code="BOM-CONCURRENCY",
            version=1,
            status=BillOfMaterials.Status.ACTIVE,
            batch_quantity=Decimal("1"),
            created_by=self.user,
        )
        BillOfMaterialsLine.objects.create(
            bom=bom,
            product=self.fabric,
            quantity=Decimal("5"),
            unit=self.meter,
            position=1,
        )
        manufacturing_order = create_manufacturing_order(
            actor=self.user,
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            bom=bom,
            number="MO-CONCURRENCY-CONSUME",
            planned_quantity=Decimal("1"),
        )
        transition_manufacturing_order(manufacturing_order=manufacturing_order, action="ready", actor=self.user)
        self._seed_stock(location=self.source, product=self.fabric, unit=self.meter, quantity="5", key="consumption-opening")
        reservation = reserve_stock(
            organization=self.organization,
            actor=self.user,
            location=self.source,
            product=self.fabric,
            unit=self.meter,
            quantity=Decimal("5"),
            production_order_id=manufacturing_order.id,
            idempotency_key="consumption-reservation",
        )
        transition_manufacturing_order(manufacturing_order=manufacturing_order, action="start", actor=self.user)
        requirement = manufacturing_order.material_requirements.get()

        results = self._run_concurrently(
            lambda _index: consume_manufacturing_materials(
                manufacturing_order=manufacturing_order,
                allocations=[
                    {
                        "requirement_id": requirement.id,
                        "reservation": reservation,
                        "quantity": Decimal("5"),
                        "disposition": ManufacturingMaterialConsumption.Disposition.CONSUMED,
                        "idempotency_key": "consumption-race",
                    }
                ],
                actor=self.user,
            )
        )
        self.assertEqual(sum(result[0] == "ok" for result in results), 2)
        self.assertEqual(ManufacturingMaterialConsumption.objects.filter(idempotency_key="consumption-race").count(), 1)
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.MovementType.PRODUCTION_CONSUMPTION).count(), 1)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, StockReservation.Status.CONSUMED)
        position = StockPosition.objects.get(location=self.source, product=self.fabric, unit=self.meter)
        self.assertEqual(position.quantity_reserved, Decimal("0"))

    def test_concurrent_delivery_and_return_are_single_application(self):
        bom = BillOfMaterials.objects.create(
            organization=self.organization,
            company=self.company,
            fashion_model=self.model,
            output_product=self.finished,
            code="BOM-CONCURRENCY-DELIVERY",
            version=1,
            status=BillOfMaterials.Status.ACTIVE,
            batch_quantity=Decimal("1"),
            created_by=self.user,
        )
        manufacturing_order = create_manufacturing_order(
            actor=self.user,
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            order=self.order,
            order_line=self.order_line,
            bom=bom,
            number="MO-CONCURRENCY-DELIVERY",
            planned_quantity=Decimal("1"),
        )
        manufacturing_order.status = manufacturing_order.Status.DONE
        manufacturing_order.produced_quantity = Decimal("1")
        manufacturing_order.actual_end = timezone.now()
        manufacturing_order.save(update_fields=("status", "produced_quantity", "actual_end", "updated_at"))
        output_movement = apply_stock_movement(
            organization=self.organization,
            actor=self.user,
            movement_type=StockMovement.MovementType.PRODUCTION_OUTPUT,
            quantity=Decimal("1"),
            product=self.finished,
            unit=self.piece,
            destination_location=self.destination,
            reference_type="manufacturing.manufacturing_order",
            reference_id=manufacturing_order.id,
            idempotency_key="delivery-concurrency-output",
        )
        ManufacturingOutputReceipt.objects.create(
            organization=self.organization,
            company=self.company,
            manufacturing_order=manufacturing_order,
            destination_location=self.destination,
            product=self.finished,
            unit=self.piece,
            stock_movement=output_movement,
            quantity=Decimal("1"),
            created_by=self.user,
        )
        delivery = create_delivery(
            order=self.order,
            number="DEL-CONCURRENCY-1",
            mode="local_delivery",
            lines=[{"order_line": self.order_line, "quantity": Decimal("1")}],
            packages=[{"code": "PKG-CONCURRENCY-1", "description": "Concurrency package", "is_sealed": True}],
            actor=self.user,
            courier_name="Concurrency courier",
            courier_reference="CONCURRENCY-TRIP-1",
        )
        for action in ("prepare", "assign", "ship"):
            delivery = transition_delivery(delivery=delivery, action=action, actor=self.user)

        proof = {
            "proof_type": "recipient_ack",
            "recipient_name": "Concurrency customer",
            "evidence_reference": "proofs/concurrency",
        }
        results = self._run_concurrently(
            lambda _index: transition_delivery(delivery=delivery, action="deliver", actor=self.user, proof=proof)
        )
        self.assertEqual(sum(result[0] == "ok" for result in results), 2)
        self.assertEqual(DeliveryProof.objects.filter(delivery=delivery).count(), 1)
        self.assertEqual(
            StockMovement.objects.filter(
                movement_type=StockMovement.MovementType.ISSUE,
                reference_type="delivery.delivery_line",
            ).count(),
            1,
        )
        delivered_position = StockPosition.objects.get(location=self.destination, product=self.finished, unit=self.piece)
        self.assertEqual(delivered_position.quantity_available, Decimal("0"))

        delivery.refresh_from_db()
        delivery_line = delivery.lines.get()
        return_results = self._run_concurrently(
            lambda _index: create_delivery_return(
                delivery=delivery,
                number="RET-CONCURRENCY-1",
                reason="Concurrent return",
                resolution=DeliveryReturn.Resolution.RETURN_ONLY,
                idempotency_key="return-concurrency-1",
                lines=[
                    {
                        "delivery_line": delivery_line,
                        "quantity": Decimal("1"),
                        "disposition": DeliveryReturnLine.Disposition.RESTOCK,
                        "destination_location": self.destination,
                    }
                ],
                actor=self.user,
            )
        )
        self.assertEqual(sum(result[0] == "ok" for result in return_results), 2)
        self.assertEqual(DeliveryReturn.objects.filter(idempotency_key="return-concurrency-1").count(), 1)
        self.assertEqual(
            StockMovement.objects.filter(
                movement_type=StockMovement.MovementType.RETURN_IN,
                reference_type="delivery.return_line",
            ).count(),
            1,
        )
        delivered_position.refresh_from_db()
        self.assertEqual(delivered_position.quantity_available, Decimal("1"))
