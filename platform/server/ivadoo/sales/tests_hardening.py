import uuid
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import Currency
from ivadoo.organizations.models import Company, Organization


class SalesHardeningTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Sales hardening", slug="sales-hardening")
        self.company = Company.objects.create(
            organization=self.organization,
            name="Maison",
            code="sales-hardening-maison",
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="C-HARD",
            display_name="Client hardening",
        )
        self.user = User.objects.create_user(
            username="sales.hardening",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        role = Role.objects.create(
            organization=self.organization,
            code="sales-hardening-manager",
            name="Sales hardening manager",
            is_active=True,
        )
        role.permissions.set(
            Permission.objects.filter(code__in=("fashion.sale.view", "fashion.sale.manage"))
        )
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.currency = Currency.objects.create(
            code="XOF",
            name="CFA Franc",
            symbol="F",
            decimal_places=0,
            rounding=Decimal("1"),
        )

    def quotation_payload(self, number, line=None):
        return {
            "company": str(self.company.id),
            "customer": str(self.customer.id),
            "currency": str(self.currency.pk),
            "number": number,
            "lines": [
                line
                or {
                    "description": "Custom garment",
                    "quantity": "1",
                    "unit_price": "50000",
                    "discount_rate": "0",
                }
            ],
        }

    def order_payload(self, number, quotation=None, line=None):
        payload = {
            "company": str(self.company.id),
            "customer": str(self.customer.id),
            "number": number,
            "lines": [
                line
                or {
                    "description": "Custom garment",
                    "quantity": "1",
                    "unit_price": "50000",
                }
            ],
        }
        if quotation is not None:
            payload["quotation"] = quotation
        return payload

    def test_order_requires_accepted_quotation(self):
        quotation = self.client.post(
            "/api/v1/sales/quotations/",
            self.quotation_payload("Q-DRAFT"),
            format="json",
        )
        self.assertEqual(quotation.status_code, status.HTTP_201_CREATED)
        response = self.client.post(
            "/api/v1/sales/orders/",
            self.order_payload("O-DRAFT", quotation.data["id"]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accepted_quotation_can_be_converted_to_order(self):
        quotation = self.client.post(
            "/api/v1/sales/quotations/",
            self.quotation_payload("Q-ACCEPT"),
            format="json",
        )
        self.client.post(f"/api/v1/sales/quotations/{quotation.data['id']}/actions/send/")
        accepted = self.client.post(
            f"/api/v1/sales/quotations/{quotation.data['id']}/actions/accept/"
        )
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        response = self.client.post(
            "/api/v1/sales/orders/",
            self.order_payload("O-ACCEPT", quotation.data["id"]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_quotation_line_rejects_invalid_numeric_values(self):
        invalid_lines = [
            {"description": "q0", "quantity": "0", "unit_price": "1", "discount_rate": "0"},
            {"description": "p0", "quantity": "1", "unit_price": "-1", "discount_rate": "0"},
            {"description": "d1", "quantity": "1", "unit_price": "1", "discount_rate": "1.0001"},
            {"description": "d0", "quantity": "1", "unit_price": "1", "discount_rate": "-0.0001"},
        ]
        for index, line in enumerate(invalid_lines):
            response = self.client.post(
                "/api/v1/sales/quotations/",
                self.quotation_payload(f"Q-BAD-{index}", line),
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_line_rejects_invalid_numeric_values(self):
        invalid_lines = [
            {"description": "q0", "quantity": "0", "unit_price": "1"},
            {"description": "p0", "quantity": "1", "unit_price": "-1"},
        ]
        for index, line in enumerate(invalid_lines):
            response = self.client.post(
                "/api/v1/sales/orders/",
                self.order_payload(f"O-BAD-{index}", line=line),
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_actions_return_not_found_for_missing_scoped_resources(self):
        missing_id = uuid.uuid4()
        quotation = self.client.post(
            f"/api/v1/sales/quotations/{missing_id}/actions/send/"
        )
        order = self.client.post(
            f"/api/v1/sales/orders/{missing_id}/actions/confirm/"
        )
        self.assertEqual(quotation.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(order.status_code, status.HTTP_404_NOT_FOUND)
