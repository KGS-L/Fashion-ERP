from decimal import Decimal

from rest_framework import status

from ivadoo.authorization.models import Permission, Role
from ivadoo.inventory.models import StockLocation, StockMovement, StockPosition

from .models import DeliveryReturn
from .tests import DeliveryApiTests


class DeliveryReturnTests(DeliveryApiTests):
    test_local_delivery_requires_timestamped_proof_and_issues_finished_stock = None
    test_partial_quantity_can_be_prepared_after_issue_63 = None
    test_pickup_follows_separate_transition_path = None
    test_preparation_requires_a_package = None
    test_user_without_delivery_scope_sees_no_deliveries = None

    def setUp(self):
        super().setUp()
        role = Role.objects.get(organization=self.organization, code="delivery-manager")
        role.permissions.add(*Permission.objects.filter(code__in=("delivery.return.view", "delivery.return.manage")))

    def _complete_local(self, *, quantity="1", number="DEL-COMPLETE-1"):
        created = self._create(quantity=quantity, number=number)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        delivery_id = created.data["id"]
        for action in ("prepare", "assign", "ship"):
            response = self.client.post(f"/api/v1/delivery/deliveries/{delivery_id}/actions/{action}/", {}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        delivered = self.client.post(
            f"/api/v1/delivery/deliveries/{delivery_id}/actions/deliver/",
            {"proof": {"proof_type": "recipient_ack", "recipient_name": "Client"}},
            format="json",
        )
        self.assertEqual(delivered.status_code, status.HTTP_200_OK)
        return delivered

    def _return(self, delivery, *, number="RET-1", key="return-1", resolution="return_only", disposition="restock", destination=None, quantity="1"):
        line_id = delivery.data["lines"][0]["id"]
        payload = {
            "delivery_id": delivery.data["id"],
            "number": number,
            "reason": "Customer return",
            "resolution": resolution,
            "idempotency_key": key,
            "lines": [
                {
                    "delivery_line_id": line_id,
                    "quantity": quantity,
                    "disposition": disposition,
                    **({"destination_location_id": str(destination.id)} if destination else {}),
                }
            ],
        }
        return self.client.post("/api/v1/delivery/returns/", payload, format="json")

    def test_two_partial_deliveries_close_the_operational_balance(self):
        first = self._complete_local(quantity="0.5", number="DEL-PART-1")
        second = self._complete_local(quantity="0.5", number="DEL-PART-2")
        self.assertEqual(first.data["status"], "delivered")
        self.assertEqual(second.data["status"], "delivered")
        balance = self.client.get(f"/api/v1/delivery/orders/{self.order.id}/balance/")
        self.assertEqual(balance.status_code, status.HTTP_200_OK)
        self.assertTrue(balance.data["fully_allocated"])
        self.assertTrue(balance.data["operationally_complete"])
        self.assertEqual(Decimal(balance.data["lines"][0]["remaining_to_allocate"]), Decimal("0"))
        position = StockPosition.objects.get(location=self.location, product=self.finished, product_variant=None, unit=self.piece)
        self.assertEqual(position.quantity_available, Decimal("0"))

    def test_delivery_cannot_overallocate_order_quantity(self):
        first = self._create(quantity="0.75", number="DEL-ALLOC-1")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self._create(quantity="0.5", number="DEL-ALLOC-2")
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_restock_return_is_idempotent_and_preserves_delivery_history(self):
        delivered = self._complete_local(number="DEL-RETURN-1")
        returned = self._return(delivered)
        self.assertEqual(returned.status_code, status.HTTP_201_CREATED)
        duplicate = self._return(delivered)
        self.assertEqual(duplicate.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate.data["id"], returned.data["id"])
        self.assertEqual(DeliveryReturn.objects.count(), 1)
        self.assertEqual(returned.data["resolution"], DeliveryReturn.Resolution.RETURN_ONLY)
        self.assertEqual(returned.data["lines"][0]["disposition"], "restock")
        self.assertTrue(returned.data["lines"][0]["stock_movements"])
        position = StockPosition.objects.get(location=self.location, product=self.finished, product_variant=None, unit=self.piece)
        self.assertEqual(position.quantity_available, Decimal("1"))
        self.assertEqual(
            StockMovement.objects.filter(reference_type="delivery.delivery_line", movement_type=StockMovement.MovementType.ISSUE).count(),
            1,
        )

    def test_damaged_return_moves_quantity_to_damaged_state(self):
        delivered = self._complete_local(number="DEL-DAMAGE-1")
        returned = self._return(delivered, number="RET-DAMAGE-1", key="return-damage-1", disposition="damaged")
        self.assertEqual(returned.status_code, status.HTTP_201_CREATED)
        position = StockPosition.objects.get(location=self.location, product=self.finished, product_variant=None, unit=self.piece)
        self.assertEqual(position.quantity_available, Decimal("0"))
        self.assertEqual(position.quantity_damaged, Decimal("1"))

    def test_quarantine_return_requires_receiving_location(self):
        delivered = self._complete_local(number="DEL-QUAR-1")
        invalid = self._return(delivered, number="RET-QUAR-X", key="return-quar-x", disposition="quarantine", destination=self.location)
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        quarantine = StockLocation.objects.create(
            warehouse=self.warehouse,
            code="return-quarantine",
            name="Return quarantine",
            kind=StockLocation.Kind.RECEIVING,
        )
        returned = self._return(delivered, number="RET-QUAR-1", key="return-quar-1", disposition="quarantine", destination=quarantine)
        self.assertEqual(returned.status_code, status.HTTP_201_CREATED)
        position = StockPosition.objects.get(location=quarantine, product=self.finished, product_variant=None, unit=self.piece)
        self.assertEqual(position.quantity_available, Decimal("1"))

    def test_exchange_return_reopens_delivery_allowance_without_erasing_history(self):
        delivered = self._complete_local(number="DEL-EXCHANGE-1")
        returned = self._return(
            delivered,
            number="RET-EXCHANGE-1",
            key="return-exchange-1",
            resolution="exchange",
        )
        self.assertEqual(returned.status_code, status.HTTP_201_CREATED)
        balance = self.client.get(f"/api/v1/delivery/orders/{self.order.id}/balance/")
        self.assertEqual(Decimal(balance.data["lines"][0]["exchange_allowance_quantity"]), Decimal("1"))
        self.assertEqual(Decimal(balance.data["lines"][0]["remaining_to_allocate"]), Decimal("1"))
        replacement = self._create(quantity="1", number="DEL-EXCHANGE-REPLACEMENT")
        self.assertEqual(replacement.status_code, status.HTTP_201_CREATED)
