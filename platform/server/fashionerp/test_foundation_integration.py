from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from fashionerp.audit.models import AuditEvent
from fashionerp.authorization.models import AccessGrant
from fashionerp.identity.services import create_api_session
from fashionerp.organizations.models import Company, Establishment, Organization


class FoundationIntegrationExitTests(APITestCase):
    databases = {"default", "tenant_b"}

    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_foundation_reference",
            database="default",
            profile="pilot",
            verbosity=0,
        )
        call_command(
            "seed_foundation_reference",
            database="tenant_b",
            profile="isolation",
            verbosity=0,
        )

    def setUp(self):
        cache.clear()

    def client_for(self, username):
        user = get_user_model().objects.get(username=username)
        _, token = create_api_session(user=user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return user, client

    def test_unauthenticated_foundation_access_is_rejected(self):
        response = self.client.get("/api/v1/companies/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.data["error"]["code"],
            "authentication_required",
        )

    def test_admin_can_follow_core_foundation_read_paths(self):
        _, client = self.client_for("foundation.admin")

        companies = client.get("/api/v1/companies/")
        establishments = client.get("/api/v1/establishments/")
        roles = client.get("/api/v1/access/roles/")
        audit = client.get("/api/v1/audit/events/")
        languages = client.get("/api/v1/i18n/languages/")

        self.assertEqual(companies.status_code, status.HTTP_200_OK)
        self.assertEqual(companies.data["count"], 1)
        self.assertEqual(establishments.status_code, status.HTTP_200_OK)
        self.assertEqual(establishments.data["count"], 2)
        self.assertEqual(roles.status_code, status.HTTP_200_OK)
        self.assertEqual(audit.status_code, status.HTTP_200_OK)
        self.assertEqual(languages.status_code, status.HTTP_200_OK)

    def test_company_scope_and_establishment_scope_return_different_datasets(self):
        _, company_client = self.client_for("company.reader")
        _, workshop_client = self.client_for("workshop.reader")

        company_companies = company_client.get("/api/v1/companies/")
        company_sites = company_client.get("/api/v1/establishments/")
        workshop_companies = workshop_client.get("/api/v1/companies/")
        workshop_sites = workshop_client.get("/api/v1/establishments/")

        self.assertEqual(company_companies.data["count"], 1)
        self.assertEqual(company_sites.data["count"], 2)

        # An establishment-scoped grant does not imply Company-level read.
        self.assertEqual(workshop_companies.data["count"], 0)
        self.assertEqual(workshop_sites.data["count"], 1)
        self.assertEqual(
            workshop_sites.data["results"][0]["code"],
            "pilot-workshop",
        )

    def test_inter_establishment_access_is_hidden_with_404(self):
        _, client = self.client_for("workshop.reader")
        store = Establishment.objects.get(code="pilot-store")

        response = client.get(
            f"/api/v1/establishments/{store.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_permission_revocation_is_effective_on_next_request(self):
        user, client = self.client_for("company.reader")
        company = Company.objects.get(code="pilot-company")

        before = client.get(f"/api/v1/companies/{company.id}/")
        self.assertEqual(before.status_code, status.HTTP_200_OK)

        AccessGrant.objects.filter(
            user=user,
            company=company,
            revoked_at__isnull=True,
        ).update(revoked_at=__import__("django").utils.timezone.now())

        after = client.get(f"/api/v1/companies/{company.id}/")
        self.assertEqual(after.status_code, status.HTTP_404_NOT_FOUND)

    def test_sensitive_admin_mutation_emits_immutable_audit_event(self):
        _, client = self.client_for("foundation.admin")
        company = Company.objects.get(code="pilot-company")

        response = client.patch(
            f"/api/v1/companies/{company.id}/",
            {"legal_name": "Updated Foundation Pilot Company"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditEvent.objects.get(
            action="foundation.company.update",
            object_id=str(company.id),
        )
        self.assertEqual(
            event.before["legal_name"],
            "Foundation Pilot Company",
        )
        self.assertEqual(
            event.after["legal_name"],
            "Updated Foundation Pilot Company",
        )

    def test_second_organization_is_physically_isolated_in_other_database(self):
        primary = Organization.objects.using("default").get()
        isolated = Organization.objects.using("tenant_b").get()

        self.assertNotEqual(primary.id, isolated.id)
        self.assertEqual(primary.slug, "foundation-pilot")
        self.assertEqual(isolated.slug, "foundation-isolation")
        self.assertFalse(
            Company.objects.using("default").filter(
                organization_id=isolated.id
            ).exists()
        )
        self.assertFalse(
            Company.objects.using("tenant_b").filter(
                organization_id=primary.id
            ).exists()
        )
