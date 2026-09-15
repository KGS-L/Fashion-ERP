from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import Product
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.organizations.models import Company, Establishment, Organization

from .models import StockLot, StockMovement, StockPosition, StockReservation


class InventoryApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Inventory", slug="inventory")
        self.company = Company.objects.create(organization=self.organization, name="Maison", code="inventory-maison")
        self.establishment = Establishment.objects.create(
            company=self.company,
            name="Atelier",
            code="atelier",
            site_type=Establishment.SiteType.WORKSHOP,
        )
        self.user = User.objects.create_user(
            username="inventory.manager",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        role = Role.objects.create(
            organization=self.organization,
            code="inventory-manager",
            name="Inventory manager",
            is_active=True,
        )
        role.permissions.set(
            Permission.objects.filter(
                code__in=("inventory.stock.view", "inventory.stock.manage", "inventory.stock.reserve")
            )
        )
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.meter = UnitOfMeasure.objects.create(
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
            code="fabric",
            name="Fabric",
            product_type=Product.ProductType.FABRIC,
            unit=self.meter,
        )
        warehouse = self.client.post(
            "/api/v1/inventory/warehouses/",
            {
                "company_id": str(self.company.id),
                "establishment_id": str(self.establishment.id),
                "code": "main",
                "name": "Main stock",
            },
            format="json",
        )
        self.assertEqual(warehouse.status_code, status.HTTP_201_CREATED)
        self.warehouse_id = warehouse.data["id"]
        location = self.client.post(
            "/api/v1/inventory/locations/",
            {"warehouse_id": self.warehouse_id, "code": "rack-a", "name": "Rack A", "kind": "internal"},
            format="json",
        )
        self.assertEqual(location.status_code, status.HTTP_201_CREATED)
        self.location_id = location.data["id"]
        second = self.client.post(
            "/api/v1/inventory/locations/",
            {"warehouse_id": self.warehouse_id, "code": "rack-b", "name": "Rack B", "kind": "internal"},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.location_b_id = second.data["id"]

    def _movement(self, *, movement_type, quantity, source=None, destination=None, key=""):
        payload = {
            "movement_type": movement_type,
            "quantity": str(quantity),
            "product_id": str(self.fabric.id),
            "unit_id": str(self.meter.id),
            "idempotency_key": key,
        }
        if source:
            payload["source_location_id"] = source
        if destination:
            payload["destination_location_id"] = destination
        return self.client.post("/api/v1/inventory/movements/apply/", payload, format="json")

    def test_adjustment_and_transfer_keep_positions_consistent(self):
        inbound = self._movement(
            movement_type="adjustment_in",
            quantity="10",
            destination=self.location_id,
            key="stock-open-1",
        )
        self.assertEqual(inbound.status_code, status.HTTP_201_CREATED)
        duplicate = self._movement(
            movement_type="adjustment_in",
            quantity="10",
            destination=self.location_id,
            key="stock-open-1",
        )
        self.assertEqual(duplicate.status_code, status.HTTP_201_CREATED)
        self.assertEqual(StockMovement.objects.filter(idempotency_key="stock-open-1").count(), 1)

        transfer = self._movement(
            movement_type="transfer",
            quantity="4",
            source=self.location_id,
            destination=self.location_b_id,
            key="transfer-1",
        )
        self.assertEqual(transfer.status_code, status.HTTP_201_CREATED)
        source = StockPosition.objects.get(location_id=self.location_id, product=self.fabric)
        destination = StockPosition.objects.get(location_id=self.location_b_id, product=self.fabric)
        self.assertEqual(source.quantity_available, Decimal("6"))
        self.assertEqual(destination.quantity_available, Decimal("4"))

    def test_outbound_cannot_make_available_stock_negative(self):
        self._movement(
            movement_type="adjustment_in",
            quantity="2",
            destination=self.location_id,
            key="negative-open",
        )
        response = self._movement(
            movement_type="issue",
            quantity="3",
            source=self.location_id,
            key="negative-issue",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        position = StockPosition.objects.get(location_id=self.location_id, product=self.fabric)
        self.assertEqual(position.quantity_available, Decimal("2"))

    def test_lot_opening_and_issue_update_remaining_quantity(self):
        lot = self.client.post(
            "/api/v1/inventory/lots/",
            {
                "warehouse_id": self.warehouse_id,
                "location_id": self.location_id,
                "product_id": str(self.fabric.id),
                "unit_id": str(self.meter.id),
                "code": "ROLL-001",
                "kind": "roll",
                "opening_quantity": "20",
                "initial_length": "20",
                "width": "1.5000",
                "origin": "BF",
            },
            format="json",
        )
        self.assertEqual(lot.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(lot.data["remaining_quantity"]), Decimal("20"))
        issue = self.client.post(
            "/api/v1/inventory/movements/apply/",
            {
                "movement_type": "issue",
                "quantity": "5",
                "product_id": str(self.fabric.id),
                "unit_id": str(self.meter.id),
                "source_location_id": self.location_id,
                "lot_id": lot.data["id"],
                "idempotency_key": "roll-issue-1",
            },
            format="json",
        )
        self.assertEqual(issue.status_code, status.HTTP_201_CREATED)
        stored = StockLot.objects.get(id=lot.data["id"])
        self.assertEqual(stored.remaining_quantity, Decimal("15"))
        self.assertEqual(stored.remaining_length, Decimal("15.0000"))

    def test_reservation_is_atomic_and_release_is_idempotent(self):
        self._movement(
            movement_type="adjustment_in",
            quantity="10",
            destination=self.location_id,
            key="reserve-open",
        )
        reservation = self.client.post(
            "/api/v1/inventory/reservations/",
            {
                "location_id": self.location_id,
                "product_id": str(self.fabric.id),
                "unit_id": str(self.meter.id),
                "quantity": "6",
                "idempotency_key": "reservation-1",
            },
            format="json",
        )
        self.assertEqual(reservation.status_code, status.HTTP_201_CREATED)
        rejected = self.client.post(
            "/api/v1/inventory/reservations/",
            {
                "location_id": self.location_id,
                "product_id": str(self.fabric.id),
                "unit_id": str(self.meter.id),
                "quantity": "5",
                "idempotency_key": "reservation-2",
            },
            format="json",
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        position = StockPosition.objects.get(location_id=self.location_id, product=self.fabric)
        self.assertEqual(position.quantity_available, Decimal("4"))
        self.assertEqual(position.quantity_reserved, Decimal("6"))

        release_url = f"/api/v1/inventory/reservations/{reservation.data['id']}/release/"
        self.assertEqual(self.client.post(release_url, {}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post(release_url, {}, format="json").status_code, status.HTTP_200_OK)
        position.refresh_from_db()
        self.assertEqual(position.quantity_available, Decimal("10"))
        self.assertEqual(position.quantity_reserved, Decimal("0"))
        stored = StockReservation.objects.get(id=reservation.data["id"])
        self.assertEqual(stored.status, StockReservation.Status.RELEASED)

    def test_user_without_inventory_scope_sees_no_warehouses(self):
        outsider = User.objects.create_user(
            username="inventory.outsider",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        _, token = create_api_session(user=outsider)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/v1/inventory/warehouses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
