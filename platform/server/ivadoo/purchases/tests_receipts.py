from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import Product
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import Currency, UnitOfMeasure
from ivadoo.inventory.models import StockLocation, StockMovement, StockPosition, Warehouse
from ivadoo.organizations.models import Company, Organization

from .models import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReceipt,
    Supplier,
    SupplierPurchaseHistory,
)


class PurchaseReceiptApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Receipt Org", slug="receipt-org")
        self.company = Company.objects.create(
            organization=self.organization,
            name="Maison Receipt",
            code="receipt-company",
        )
        self.currency = Currency.objects.create(
            code="XOF",
            name="West African CFA franc",
            symbol="FCFA",
            decimal_places=0,
            rounding=Decimal("1"),
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
        self.product = Product.objects.create(
            organization=self.organization,
            company=self.company,
            code="fabric-receipt",
            name="Fabric receipt",
            product_type=Product.ProductType.FABRIC,
            unit=self.unit,
        )
        self.warehouse = Warehouse.objects.create(
            organization=self.organization,
            company=self.company,
            code="main",
            name="Main warehouse",
        )
        self.location = StockLocation.objects.create(
            warehouse=self.warehouse,
            code="receiving",
            name="Receiving",
            kind=StockLocation.Kind.RECEIVING,
        )
        self.supplier = Supplier.objects.create(
            organization=self.organization,
            company=self.company,
            code="supplier-receipt",
            name="Supplier receipt",
            currency=self.currency,
        )
        self.user = User.objects.create_user(
            username="receipt.manager",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        permissions = (
            "purchase.supplier.view",
            "purchase.receipt.view",
            "purchase.receipt.manage",
            "purchase.receipt.control",
            "purchase.receipt.post",
        )
        role = Role.objects.create(
            organization=self.organization,
            code="receipt-manager",
            name="Receipt manager",
            is_active=True,
        )
        role.permissions.set(Permission.objects.filter(code__in=permissions))
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.purchase_order = PurchaseOrder.objects.create(
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            supplier=self.supplier,
            currency=self.currency,
            number="PO-RECEIPT-1",
            status=PurchaseOrder.Status.ORDERED,
            created_by=self.user,
        )
        self.po_line = PurchaseOrderLine.objects.create(
            purchase_order=self.purchase_order,
            product=self.product,
            unit=self.unit,
            quantity=Decimal("10"),
            unit_price=Decimal("2500"),
        )

    def create_receipt(self, number, quantity):
        response = self.client.post(
            "/api/v1/purchases/receipts/",
            {
                "purchase_order_id": str(self.purchase_order.id),
                "warehouse_id": str(self.warehouse.id),
                "number": number,
                "lines": [
                    {
                        "purchase_order_line_id": str(self.po_line.id),
                        "location_id": str(self.location.id),
                        "received_quantity": str(quantity),
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def control(self, receipt, accepted, rejected):
        line_id = receipt["lines"][0]["id"]
        response = self.client.post(
            f"/api/v1/purchases/receipts/{receipt['id']}/actions/",
            {
                "action": "control",
                "lines": [
                    {
                        "line_id": line_id,
                        "accepted_quantity": str(accepted),
                        "rejected_quantity": str(rejected),
                        "note": "Incoming control",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data

    def post_receipt(self, receipt_id):
        return self.client.post(
            f"/api/v1/purchases/receipts/{receipt_id}/actions/",
            {"action": "post"},
            format="json",
        )

    def test_partial_receipt_only_books_accepted_stock_and_keeps_remainder_open(self):
        receipt = self.create_receipt("RCPT-1", "10.0000")
        controlled = self.control(receipt, "8.0000", "2.0000")
        self.assertEqual(controlled["status"], PurchaseReceipt.Status.CONTROLLED)
        posted = self.post_receipt(receipt["id"])
        self.assertEqual(posted.status_code, status.HTTP_200_OK, posted.data)
        self.assertEqual(posted.data["status"], PurchaseReceipt.Status.POSTED)

        self.po_line.refresh_from_db()
        self.assertEqual(self.po_line.received_quantity, Decimal("8"))
        position = StockPosition.objects.get(
            organization=self.organization,
            location=self.location,
            product=self.product,
            product_variant=None,
            unit=self.unit,
        )
        self.assertEqual(position.quantity_available, Decimal("8"))
        movement = StockMovement.objects.get(reference_type="purchases.receipt_line")
        self.assertEqual(movement.quantity, Decimal("8"))
        self.assertEqual(SupplierPurchaseHistory.objects.count(), 1)

        replacement = self.create_receipt("RCPT-2", "2.0000")
        self.control(replacement, "2.0000", "0.0000")
        replacement_post = self.post_receipt(replacement["id"])
        self.assertEqual(replacement_post.status_code, status.HTTP_200_OK)
        self.po_line.refresh_from_db()
        self.assertEqual(self.po_line.received_quantity, Decimal("10"))
        position.refresh_from_db()
        self.assertEqual(position.quantity_available, Decimal("10"))

    def test_post_is_idempotent_and_does_not_duplicate_stock_or_history(self):
        receipt = self.create_receipt("RCPT-IDEMP", "4.0000")
        self.control(receipt, "4.0000", "0.0000")
        first = self.post_receipt(receipt["id"])
        second = self.post_receipt(receipt["id"])
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(StockMovement.objects.filter(reference_type="purchases.receipt_line").count(), 1)
        self.assertEqual(SupplierPurchaseHistory.objects.count(), 1)
        self.po_line.refresh_from_db()
        self.assertEqual(self.po_line.received_quantity, Decimal("4"))

    def test_over_receipt_is_rejected_before_posting(self):
        response = self.client.post(
            "/api/v1/purchases/receipts/",
            {
                "purchase_order_id": str(self.purchase_order.id),
                "warehouse_id": str(self.warehouse.id),
                "number": "RCPT-OVER",
                "lines": [
                    {
                        "purchase_order_line_id": str(self.po_line.id),
                        "location_id": str(self.location.id),
                        "received_quantity": "11.0000",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_supplier_performance_is_derived_from_posted_receipts(self):
        receipt = self.create_receipt("RCPT-PERF", "10.0000")
        self.control(receipt, "9.0000", "1.0000")
        self.assertEqual(self.post_receipt(receipt["id"]).status_code, status.HTTP_200_OK)
        response = self.client.get(
            f"/api/v1/purchases/suppliers/{self.supplier.id}/performance/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["receipt_count"], 1)
        self.assertEqual(response.data["line_count"], 1)
        self.assertEqual(Decimal(response.data["total_received"]), Decimal("10"))
        self.assertEqual(Decimal(response.data["total_accepted"]), Decimal("9"))
        self.assertEqual(Decimal(response.data["acceptance_rate"]), Decimal("90"))
