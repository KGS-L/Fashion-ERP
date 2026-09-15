from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from fashionerp.authorization.models import AccessGrant, Permission, Role
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


class CustomerScopeTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Scoped Tenant", slug="scoped-tenant")
        self.company_a = Company.objects.create(
            organization=self.organization, name="Company A", code="company-a"
        )
        self.company_b = Company.objects.create(
            organization=self.organization, name="Company B", code="company-b"
        )
        self.site_a1 = Establishment.objects.create(
            company=self.company_a, name="A1", code="a1"
        )
        self.site_a2 = Establishment.objects.create(
            company=self.company_a, name="A2", code="a2"
        )
        self.customer_a1 = Customer.objects.create(
            organization=self.organization, company=self.company_a,
            establishment=self.site_a1, code="A1-C", display_name="A1 Customer"
        )
        self.customer_a2 = Customer.objects.create(
            organization=self.organization, company=self.company_a,
            establishment=self.site_a2, code="A2-C", display_name="A2 Customer"
        )
        self.customer_b = Customer.objects.create(
            organization=self.organization, company=self.company_b,
            code="B-C", display_name="B Customer"
        )
        self.user = get_user_model().objects.create_user(
            username="scoped.customer.user",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        self.view_permission = Permission.objects.get(code="fashion.customer.view")
        self.manage_permission = Permission.objects.get(code="fashion.customer.manage")

    def authenticate(self):
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def role(self, code, *permissions):
        role = Role.objects.create(
            organization=self.organization, code=code, name=code, is_active=True
        )
        role.permissions.set(permissions)
        return role

    def test_establishment_scope_only_lists_its_customers(self):
        role = self.role("site-customer-viewer", self.view_permission)
        grant = AccessGrant.objects.create(
            user=self.user, role=role, establishment=self.site_a1
        )
        self.authenticate()
        response = self.client.get("/api/v1/customers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {str(self.customer_a1.id)})

        detail = self.client.get(f"/api/v1/customers/{self.customer_a2.id}/")
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_company_scope_lists_all_company_customers_only(self):
        role = self.role("company-customer-viewer", self.view_permission)
        AccessGrant.objects.create(user=self.user, role=role, company=self.company_a)
        self.authenticate()
        response = self.client.get("/api/v1/customers/")
        ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(ids, {str(self.customer_a1.id), str(self.customer_a2.id)})

    def test_manage_scope_does_not_imply_view_scope(self):
        role = self.role("customer-manager", self.manage_permission)
        AccessGrant.objects.create(user=self.user, role=role, company=self.company_a)
        self.authenticate()
        response = self.client.get("/api/v1/customers/")
        self.assertEqual(response.data["count"], 0)

    def test_revocation_is_effective_on_next_request(self):
        role = self.role("revocable-customer-viewer", self.view_permission)
        grant = AccessGrant.objects.create(user=self.user, role=role, company=self.company_a)
        self.authenticate()
        self.assertEqual(self.client.get("/api/v1/customers/").data["count"], 2)

        from django.utils import timezone
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])

        response = self.client.get("/api/v1/customers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_manage_cannot_create_outside_grant_scope(self):
        role = self.role("site-customer-manager", self.manage_permission)
        AccessGrant.objects.create(user=self.user, role=role, establishment=self.site_a1)
        self.authenticate()
        response = self.client.post(
            "/api/v1/customers/",
            {
                "company_id": str(self.company_a.id),
                "establishment_id": str(self.site_a2.id),
                "customer_type": "individual",
                "code": "DENIED",
                "display_name": "Denied Customer",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
