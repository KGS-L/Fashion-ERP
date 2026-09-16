from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.catalog.models import FashionModel, FashionModelVariant
from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.operations.models import ApprovalRule
from ivadoo.organizations.models import Company, Organization

from .models import Order, OrderCommercialSnapshot


class CommercialOrderApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Commercial Orders",
            slug="commercial-orders",
        )
        self.company = Company.objects.create(
            organization=self.organization,
            name="Maison Series",
            code="maison-series",
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="WHOLESALE-001",
            display_name="Wholesale Customer",
        )
        self.creator = User.objects.create_user(
            username="commercial.creator",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        self.sales_role = Role.objects.create(
            organization=self.organization,
            code="commercial-manager",
            name="Commercial manager",
            is_active=True,
        )
        self.sales_role.permissions.set(
            Permission.objects.filter(
                code__in=("fashion.sale.view", "fashion.sale.manage")
            )
        )
        AccessGrant.objects.create(
            user=self.creator,
            role=self.sales_role,
            company=self.company,
        )
        _, token = create_api_session(user=self.creator)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.model = FashionModel.objects.create(
            organization=self.organization,
            company=self.company,
            code="TEE-2026",
            name="Series Tee",
        )
        self.small = FashionModelVariant.objects.create(
            fashion_model=self.model,
            code="TEE-S-BLACK",
            size="S",
            color="Black",
        )
        self.medium = FashionModelVariant.objects.create(
            fashion_model=self.model,
            code="TEE-M-BLACK",
            size="M",
            color="Black",
        )

    def _series_payload(self, *, number="SO-001", discount_rate="0.1000"):
        return {
            "company": str(self.company.id),
            "customer": str(self.customer.id),
            "number": number,
            "order_type": "series",
            "delivery_date": "2026-10-20",
            "event_date": "2026-10-25",
            "lines": [
                {
                    "fashion_model": str(self.model.id),
                    "description": "Series production",
                    "quantity": "3.0000",
                    "unit_price": "10000.0000",
                    "discount_rate": discount_rate,
                    "fulfillment_mode": "production",
                    "commercial_customization": {"label": "Club Edition"},
                    "variant_quantities": [
                        {
                            "model_variant": str(self.small.id),
                            "quantity": "1.0000",
                            "commercial_customization": {"print": "front"},
                        },
                        {
                            "model_variant": str(self.medium.id),
                            "quantity": "2.0000",
                        },
                    ],
                }
            ],
        }

    def test_series_order_records_variant_matrix_and_confirmation_snapshot(self):
        response = self.client.post(
            "/api/v1/sales/orders/",
            self._series_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["order_type"], "series")
        self.assertEqual(len(response.data["lines"][0]["variant_quantities"]), 2)
        self.assertEqual(response.data["lines"][0]["variant_quantities"][0]["size"], "S")
        self.assertEqual(response.data["lines"][0]["variant_quantities"][0]["color"], "Black")

        confirmed = self.client.post(
            f"/api/v1/sales/orders/{response.data['id']}/actions/confirm/"
        )
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK, confirmed.data)
        self.assertEqual(confirmed.data["status"], "confirmed")
        self.assertEqual(confirmed.data["commercial_snapshot"]["order_type"], "series")
        self.assertEqual(
            Decimal(confirmed.data["commercial_snapshot"]["subtotal"]),
            Decimal("30000.0000"),
        )
        self.assertEqual(
            Decimal(confirmed.data["commercial_snapshot"]["discount_total"]),
            Decimal("3000.0000"),
        )
        self.assertEqual(
            Decimal(confirmed.data["commercial_snapshot"]["total"]),
            Decimal("27000.0000"),
        )
        snapshot = OrderCommercialSnapshot.objects.get(order_id=response.data["id"])
        self.assertEqual(snapshot.payload["lines"][0]["variant_quantities"][1]["quantity"], "2.0000")

    def test_series_order_requires_variant_quantity_sum_to_match_line(self):
        payload = self._series_payload(number="SO-002")
        payload["lines"][0]["quantity"] = "4.0000"
        response = self.client.post("/api/v1/sales/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_series_order_rejects_model_from_another_company_scope(self):
        other_company = Company.objects.create(
            organization=self.organization,
            name="Other Maison",
            code="other-maison-series",
        )
        other_model = FashionModel.objects.create(
            organization=self.organization,
            company=other_company,
            code="OTHER-TEE",
            name="Other Tee",
        )
        other_small = FashionModelVariant.objects.create(
            fashion_model=other_model,
            code="OTHER-S",
            size="S",
            color="Blue",
        )
        other_medium = FashionModelVariant.objects.create(
            fashion_model=other_model,
            code="OTHER-M",
            size="M",
            color="Blue",
        )
        payload = self._series_payload(number="SO-SCOPE")
        payload["lines"][0]["fashion_model"] = str(other_model.id)
        payload["lines"][0]["variant_quantities"] = [
            {"model_variant": str(other_small.id), "quantity": "1.0000"},
            {"model_variant": str(other_medium.id), "quantity": "2.0000"},
        ]
        response = self.client.post("/api/v1/sales/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wholesale_order_rejects_invalid_discount(self):
        payload = self._series_payload(number="WO-001", discount_rate="1.1000")
        payload["order_type"] = "wholesale"
        response = self.client.post("/api/v1/sales/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delivery_date_must_not_follow_event_date(self):
        payload = self._series_payload(number="SO-DATES")
        payload["delivery_date"] = "2026-10-30"
        payload["event_date"] = "2026-10-25"
        response = self.client.post("/api/v1/sales/orders/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_configured_amount_and_discount_rules_require_distinct_sales_approver(self):
        ApprovalRule.objects.create(
            organization=self.organization,
            company=self.company,
            resource=ApprovalRule.Resource.SALES_ORDER,
            action="confirm_amount",
            threshold=Decimal("20000.0000"),
            require_distinct_approver=True,
        )
        ApprovalRule.objects.create(
            organization=self.organization,
            company=self.company,
            resource=ApprovalRule.Resource.SALES_ORDER,
            action="confirm_discount",
            threshold=Decimal("0.0500"),
            require_distinct_approver=True,
        )
        created = self.client.post(
            "/api/v1/sales/orders/",
            self._series_payload(number="SO-APPROVAL"),
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)

        blocked = self.client.post(
            f"/api/v1/sales/orders/{created.data['id']}/actions/confirm/"
        )
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Order.objects.get(id=created.data["id"]).status, Order.Status.DRAFT)

        approver = User.objects.create_user(
            username="commercial.approver",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        approver_role = Role.objects.create(
            organization=self.organization,
            code="commercial-approver",
            name="Commercial approver",
            is_active=True,
        )
        approver_role.permissions.set(
            Permission.objects.filter(
                code__in=(
                    "fashion.sale.view",
                    "fashion.sale.manage",
                    "fashion.sale.approve",
                )
            )
        )
        AccessGrant.objects.create(
            user=approver,
            role=approver_role,
            company=self.company,
        )
        _, approver_token = create_api_session(user=approver)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {approver_token}")

        confirmed = self.client.post(
            f"/api/v1/sales/orders/{created.data['id']}/actions/confirm/"
        )
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK, confirmed.data)
        self.assertEqual(confirmed.data["commercial_snapshot"]["confirmed_by_id"], str(approver.id))
