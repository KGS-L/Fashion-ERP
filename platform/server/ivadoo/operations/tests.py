from decimal import Decimal

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import Product
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import Currency, UnitOfMeasure
from ivadoo.inventory.models import StockLocation, StockMovement, Warehouse
from ivadoo.organizations.models import Company, Establishment, Organization
from ivadoo.purchases.models import PurchaseOrder, PurchaseOrderLine, Supplier
from ivadoo.purchases.procurement_services import transition_purchase_order

from .models import ApprovalRule, StockMovementApproval


class OperationalApprovalTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Approval test", slug="approval-test")
        self.company = Company.objects.create(organization=self.organization, name="Maison", code="approval-maison")
        self.establishment = Establishment.objects.create(company=self.company, name="Atelier", code="approval-atelier", site_type=Establishment.SiteType.WORKSHOP)
        self.warehouse = Warehouse.objects.create(organization=self.organization, company=self.company, establishment=self.establishment, code="main", name="Main")
        self.location = StockLocation.objects.create(warehouse=self.warehouse, code="rack", name="Rack", kind=StockLocation.Kind.INTERNAL)
        self.unit = UnitOfMeasure.objects.create(organization=self.organization, code="m", name="Meter", symbol="m", category="length", ratio_to_base=Decimal("1"), rounding=Decimal("0.01"))
        self.product = Product.objects.create(organization=self.organization, company=self.company, code="fabric", name="Fabric", product_type=Product.ProductType.FABRIC, unit=self.unit)
        self.currency = Currency.objects.create(code="XOF", name="West African CFA franc", symbol="FCFA", decimal_places=0, rounding=Decimal("1"))
        self.supplier = Supplier.objects.create(organization=self.organization, company=self.company, code="supplier", name="Supplier", currency=self.currency)
        self.requester = User.objects.create_user(username="approval.requester", password="Strong-Test-Password-42!", organization=self.organization)
        self.approver = User.objects.create_user(username="approval.approver", password="Strong-Test-Password-42!", organization=self.organization)

        requester_role = Role.objects.create(organization=self.organization, code="approval-requester", name="Approval requester", is_active=True)
        requester_role.permissions.set(Permission.objects.filter(code__in=(
            "inventory.stock.view", "inventory.stock.manage", "operations.approval.view", "operations.approval.approve",
        )))
        approver_role = Role.objects.create(organization=self.organization, code="approval-approver", name="Approval approver", is_active=True)
        approver_role.permissions.set(Permission.objects.filter(code__in=("operations.approval.view", "operations.approval.approve")))
        AccessGrant.objects.create(user=self.requester, role=requester_role, company=self.company)
        AccessGrant.objects.create(user=self.approver, role=approver_role, company=self.company)
        self._authenticate(self.requester)

    def _authenticate(self, user):
        _, token = create_api_session(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _stock_payload(self, *, approval_id=None):
        payload = {
            "movement_type": "adjustment_out",
            "quantity": "2.0000",
            "product_id": str(self.product.id),
            "unit_id": str(self.unit.id),
            "source_location_id": str(self.location.id),
            "reason": "Controlled adjustment",
            "idempotency_key": "controlled-adjustment-1",
        }
        if approval_id:
            payload["approval_id"] = str(approval_id)
        return payload

    def test_scoped_stock_threshold_cannot_be_bypassed_and_retry_is_idempotent(self):
        inbound = self.client.post("/api/v1/inventory/movements/apply/", {
            "movement_type": "adjustment_in",
            "quantity": "5.0000",
            "product_id": str(self.product.id),
            "unit_id": str(self.unit.id),
            "destination_location_id": str(self.location.id),
            "idempotency_key": "approval-opening",
        }, format="json")
        self.assertEqual(inbound.status_code, status.HTTP_201_CREATED)
        ApprovalRule.objects.create(
            organization=self.organization,
            company=self.company,
            establishment=self.establishment,
            warehouse=self.warehouse,
            resource=ApprovalRule.Resource.STOCK_MOVEMENT,
            action=StockMovement.MovementType.ADJUSTMENT_OUT,
            threshold=Decimal("2"),
            require_distinct_approver=True,
        )
        blocked = self.client.post("/api/v1/inventory/movements/apply/", self._stock_payload(), format="json")
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(StockMovement.objects.filter(idempotency_key="controlled-adjustment-1").count(), 0)

        requested = self.client.post("/api/v1/operations/stock-movement-approvals/", self._stock_payload(), format="json")
        self.assertEqual(requested.status_code, status.HTTP_201_CREATED)
        approval_id = requested.data["id"]
        self.assertEqual(requested.data["status"], StockMovementApproval.Status.PENDING)

        same_actor = self.client.post(f"/api/v1/operations/stock-movement-approvals/{approval_id}/decision/", {"decision": "approve"}, format="json")
        self.assertEqual(same_actor.status_code, status.HTTP_400_BAD_REQUEST)

        self._authenticate(self.approver)
        decided = self.client.post(f"/api/v1/operations/stock-movement-approvals/{approval_id}/decision/", {"decision": "approve"}, format="json")
        self.assertEqual(decided.status_code, status.HTTP_200_OK)
        self.assertEqual(decided.data["status"], StockMovementApproval.Status.APPROVED)

        self._authenticate(self.requester)
        first = self.client.post("/api/v1/inventory/movements/apply/", self._stock_payload(approval_id=approval_id), format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        retry = self.client.post("/api/v1/inventory/movements/apply/", self._stock_payload(approval_id=approval_id), format="json")
        self.assertEqual(retry.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["id"], retry.data["id"])
        approval = StockMovementApproval.objects.get(id=approval_id)
        self.assertIsNotNone(approval.consumed_at)
        self.assertEqual(str(approval.consumed_movement_id), str(first.data["id"]))

    def test_purchase_order_rule_can_require_distinct_approver(self):
        order = PurchaseOrder.objects.create(
            organization=self.organization,
            company=self.company,
            warehouse=self.warehouse,
            supplier=self.supplier,
            currency=self.currency,
            number="PO-APPROVAL-1",
            created_by=self.requester,
        )
        PurchaseOrderLine.objects.create(
            purchase_order=order,
            product=self.product,
            unit=self.unit,
            quantity=Decimal("2"),
            unit_price=Decimal("100"),
        )
        ApprovalRule.objects.create(
            organization=self.organization,
            company=self.company,
            establishment=self.establishment,
            warehouse=self.warehouse,
            resource=ApprovalRule.Resource.PURCHASE_ORDER,
            action="approve",
            threshold=Decimal("100"),
            require_distinct_approver=True,
        )
        order = transition_purchase_order(purchase_order=order, action="submit", actor=self.requester)
        with self.assertRaises(ValidationError):
            transition_purchase_order(purchase_order=order, action="approve", actor=self.requester)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.Status.PENDING_APPROVAL)
        approved = transition_purchase_order(purchase_order=order, action="approve", actor=self.approver)
        self.assertEqual(approved.status, PurchaseOrder.Status.APPROVED)
        self.assertEqual(approved.approved_by_id, self.approver.id)
