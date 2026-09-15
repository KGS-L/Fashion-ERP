from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import Product
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import Currency, UnitOfMeasure
from ivadoo.organizations.models import Company, Organization

from .models import PurchaseOrder, PurchaseRequest, RequestForQuotation, Supplier, SupplierQuotation


class ProcurementApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Procurement", slug="procurement")
        self.company = Company.objects.create(organization=self.organization, name="Maison A", code="maison-a")
        self.other_company = Company.objects.create(organization=self.organization, name="Maison B", code="maison-b")
        self.currency = Currency.objects.create(code="XOF", name="West African CFA franc", symbol="FCFA", decimal_places=0, rounding=Decimal("1"))
        self.unit = UnitOfMeasure.objects.create(organization=self.organization, code="m", name="Meter", symbol="m", category="length", ratio_to_base=Decimal("1"), rounding=Decimal("0.01"))
        self.product = Product.objects.create(organization=self.organization, company=self.company, code="wax", name="Wax", product_type=Product.ProductType.FABRIC, unit=self.unit)
        self.supplier_a = Supplier.objects.create(organization=self.organization, company=self.company, code="supplier-a", name="Supplier A", currency=self.currency)
        self.supplier_b = Supplier.objects.create(organization=self.organization, company=self.company, code="supplier-b", name="Supplier B", currency=self.currency)
        self.hidden_supplier = Supplier.objects.create(organization=self.organization, company=self.other_company, code="hidden", name="Hidden supplier", currency=self.currency)
        self.user = User.objects.create_user(username="procurement.manager", password="Strong-Test-Password-42!", organization=self.organization)
        codes = (
            "purchase.supplier.view", "purchase.supplier.manage",
            "purchase.request.view", "purchase.request.manage", "purchase.request.approve",
            "purchase.rfq.view", "purchase.rfq.manage",
            "purchase.order.view", "purchase.order.manage", "purchase.order.approve",
        )
        role = Role.objects.create(organization=self.organization, code="procurement-manager", name="Procurement manager", is_active=True)
        role.permissions.set(Permission.objects.filter(code__in=codes))
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def request_payload(self):
        return {
            "company_id": str(self.company.id),
            "number": "PR-0001",
            "needed_by": "2026-10-01",
            "lines": [{"product_id": str(self.product.id), "unit_id": str(self.unit.id), "quantity": "20.0000", "need_reference_type": "sales.order"}],
        }

    def create_approved_request(self):
        response = self.client.post("/api/v1/purchases/requests/", self.request_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        request_id = response.data["id"]
        submitted = self.client.post(f"/api/v1/purchases/requests/{request_id}/actions/", {"action": "submit"}, format="json")
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        approved = self.client.post(f"/api/v1/purchases/requests/{request_id}/actions/", {"action": "approve"}, format="json")
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.assertEqual(approved.data["status"], PurchaseRequest.Status.APPROVED)
        return request_id

    def test_purchase_request_transitions_are_explicit_and_direct_status_patch_is_ignored(self):
        created = self.client.post("/api/v1/purchases/requests/", self.request_payload(), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        request_id = created.data["id"]
        patched = self.client.patch(f"/api/v1/purchases/requests/{request_id}/", {"status": "approved"}, format="json")
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data["status"], PurchaseRequest.Status.DRAFT)
        submitted = self.client.post(f"/api/v1/purchases/requests/{request_id}/actions/", {"action": "submit"}, format="json")
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        approved = self.client.post(f"/api/v1/purchases/requests/{request_id}/actions/", {"action": "approve"}, format="json")
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.assertEqual(approved.data["status"], PurchaseRequest.Status.APPROVED)

    def test_rfq_quote_comparison_selection_and_purchase_order_trace(self):
        request_id = self.create_approved_request()
        rfq = self.client.post("/api/v1/purchases/rfqs/", {
            "company_id": str(self.company.id), "purchase_request_id": request_id,
            "number": "RFQ-0001", "currency_code": "XOF",
            "supplier_ids": [str(self.supplier_a.id), str(self.supplier_b.id)],
        }, format="json")
        self.assertEqual(rfq.status_code, status.HTTP_201_CREATED)
        rfq_id = rfq.data["id"]
        sent = self.client.post(f"/api/v1/purchases/rfqs/{rfq_id}/actions/", {"action": "send"}, format="json")
        self.assertEqual(sent.status_code, status.HTTP_200_OK)
        self.assertEqual(sent.data["status"], RequestForQuotation.Status.SENT)

        quotes = []
        for supplier, price, lead in ((self.supplier_a, "2500.0000", 5), (self.supplier_b, "2300.0000", 7)):
            quote = self.client.post(f"/api/v1/purchases/rfqs/{rfq_id}/quotes/", {
                "supplier_id": str(supplier.id),
                "lines": [{"product_id": str(self.product.id), "unit_id": str(self.unit.id), "quantity": "20.0000", "unit_price": price, "lead_time_days": lead}],
            }, format="json")
            self.assertEqual(quote.status_code, status.HTTP_201_CREATED)
            quotes.append(quote.data)

        comparison = self.client.get(f"/api/v1/purchases/rfqs/{rfq_id}/comparison/")
        self.assertEqual(comparison.status_code, status.HTTP_200_OK)
        self.assertEqual(str(comparison.data[0]["supplier_id"]), str(self.supplier_b.id))
        selected = self.client.post(f"/api/v1/purchases/rfqs/{rfq_id}/quotes/{quotes[1]['id']}/select/", {}, format="json")
        self.assertEqual(selected.status_code, status.HTTP_200_OK)
        self.assertEqual(selected.data["status"], SupplierQuotation.Status.SELECTED)

        purchase_order = self.client.post("/api/v1/purchases/orders/", {
            "company_id": str(self.company.id), "supplier_id": str(self.supplier_b.id),
            "purchase_request_id": request_id, "rfq_id": rfq_id, "quotation_id": selected.data["id"],
            "currency_code": "XOF", "number": "PO-0001",
            "lines": [{"product_id": str(self.product.id), "unit_id": str(self.unit.id), "quantity": "20.0000", "unit_price": "2300.0000"}],
        }, format="json")
        self.assertEqual(purchase_order.status_code, status.HTTP_201_CREATED)
        po_id = purchase_order.data["id"]
        for action, expected in (("submit", PurchaseOrder.Status.PENDING_APPROVAL), ("approve", PurchaseOrder.Status.APPROVED), ("order", PurchaseOrder.Status.ORDERED)):
            response = self.client.post(f"/api/v1/purchases/orders/{po_id}/actions/", {"action": action}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["status"], expected)
        stored = PurchaseOrder.objects.get(id=po_id)
        self.assertEqual(str(stored.purchase_request_id), request_id)
        self.assertEqual(str(stored.rfq_id), rfq_id)
        self.assertEqual(str(stored.quotation_id), selected.data["id"])

    def test_cross_company_supplier_is_rejected_and_hidden(self):
        response = self.client.post("/api/v1/purchases/rfqs/", {
            "company_id": str(self.company.id), "number": "RFQ-X", "currency_code": "XOF",
            "supplier_ids": [str(self.hidden_supplier.id)],
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        hidden = self.client.get(f"/api/v1/purchases/suppliers/{self.hidden_supplier.id}/")
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)
