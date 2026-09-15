from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from fashionerp.authorization.models import Permission, Role
from fashionerp.authorization.services import grant_organization_admin
from fashionerp.identity.services import create_api_session
from fashionerp.internationalization.models import Currency
from fashionerp.organizations.models import Company, Establishment, Organization

from .models import Customer


class CustomerMasterDataTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Mode Tenant", slug="mode-tenant")
        self.company = Company.objects.create(
            organization=self.organization, name="Maison Mode", code="maison-mode"
        )
        self.site = Establishment.objects.create(
            company=self.company, name="Atelier", code="atelier",
            site_type=Establishment.SiteType.WORKSHOP,
        )
        self.currency = Currency.objects.create(
            code="XTS", name="Test currency", symbol="T", decimal_places=2,
            rounding="0.01", is_active=True,
        )
        self.admin = get_user_model().objects.create_user(
            username="mode.admin", password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        grant_organization_admin(user=self.admin)
        _, token = create_api_session(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_individual_customer_with_nested_master_data(self):
        response = self.client.post(
            "/api/v1/customers/",
            {
                "company_id": str(self.company.id),
                "establishment_id": str(self.site.id),
                "customer_type": "individual",
                "code": "CUS-0001",
                "display_name": "Awa Test",
                "first_name": "Awa",
                "last_name": "Test",
                "language_code": "fr",
                "preferred_currency_id": self.currency.id,
                "contacts": [
                    {"contact_type": "whatsapp", "value": "+22600000000", "is_primary": True}
                ],
                "addresses": [
                    {"address_type": "home", "address_line1": "Test address", "city": "Ouagadougou", "country_code": "BF", "is_primary": True}
                ],
                "consents": [
                    {"consent_type": "data_processing", "granted": True, "source": "in_person"}
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        customer = Customer.objects.get(code="CUS-0001")
        self.assertEqual(customer.organization_id, self.organization.id)
        self.assertEqual(customer.contacts.count(), 1)
        self.assertEqual(customer.addresses.count(), 1)
        self.assertEqual(customer.consents.count(), 1)

    def test_customer_requires_explicit_business_permission(self):
        user = get_user_model().objects.create_user(
            username="no.customer.access",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        _, token = create_api_session(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/v1/customers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_company_customer_cannot_use_establishment_from_other_company(self):
        other = Company.objects.create(
            organization=self.organization, name="Other", code="other"
        )
        other_site = Establishment.objects.create(
            company=other, name="Other Site", code="other-site"
        )
        response = self.client.post(
            "/api/v1/customers/",
            {
                "company_id": str(self.company.id),
                "establishment_id": str(other_site.id),
                "customer_type": "company",
                "code": "CUS-INVALID",
                "display_name": "Invalid",
                "legal_name": "Invalid SARL",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
