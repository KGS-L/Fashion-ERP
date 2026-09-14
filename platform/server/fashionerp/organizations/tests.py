import unittest
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APITestCase

from fashionerp.authorization.services import grant_organization_admin
from fashionerp.identity.authentication import resolve_api_session
from fashionerp.identity.models import ApiSession
from fashionerp.identity.services import create_api_session, digest_token

from .models import Company, Establishment, Organization
from .services import provision_local_organization


class OrganizationInvariantTests(TestCase):
    def test_database_allows_only_one_local_organization(self):
        provision_local_organization(name="Tenant A", slug="tenant-a")

        with self.assertRaises(ValidationError):
            provision_local_organization(name="Tenant B", slug="tenant-b")

    def test_database_constraint_blocks_second_organization(self):
        Organization.objects.create(name="Tenant A", slug="tenant-a")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Organization.objects.create(name="Tenant B", slug="tenant-b")


class OrganizationApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Tenant A",
            slug="tenant-a",
        )
        self.user = get_user_model().objects.create_user(
            username="tenant-a.user",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        grant_organization_admin(user=self.user)
        session, self.token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_list_only_returns_authenticated_users_organization(self):
        response = self.client.get("/api/v1/organizations/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(str(response.data[0]["id"]), str(self.organization.id))

    def test_organization_creation_is_not_exposed_by_api(self):
        response = self.client.post(
            "/api/v1/organizations/",
            {"name": "Tenant B", "slug": "tenant-b"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_unknown_organization_uuid_returns_not_found(self):
        response = self.client.get(
            f"/api/v1/organizations/{uuid.uuid4()}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "not_found")


TENANT_B_AVAILABLE = "tenant_b" in settings.DATABASES


@unittest.skipUnless(TENANT_B_AVAILABLE, "tenant_b database alias is not configured")
class PhysicalDatabaseIsolationTests(TestCase):
    databases = {"default", "tenant_b"} if TENANT_B_AVAILABLE else {"default"}

    def test_customer_databases_are_physically_isolated(self):
        org_a = Organization.objects.using("default").create(
            name="Tenant A",
            slug="tenant-a",
        )
        org_b = Organization.objects.using("tenant_b").create(
            name="Tenant B",
            slug="tenant-b",
        )

        user_model = get_user_model()
        user_a = user_model.objects.db_manager("default").create_user(
            username="tenant-a.user",
            password="Strong-A-Password-42!",
            organization=org_a,
        )
        user_model.objects.db_manager("tenant_b").create_user(
            username="tenant-b.user",
            password="Strong-B-Password-42!",
            organization=org_b,
        )

        session_a, raw_token_a = create_api_session(user=user_a)

        self.assertFalse(
            Organization.objects.using("tenant_b").filter(pk=org_a.pk).exists()
        )
        self.assertFalse(
            user_model.objects.using("tenant_b").filter(pk=user_a.pk).exists()
        )
        self.assertFalse(
            ApiSession.objects.using("tenant_b").filter(
                token_digest=digest_token(raw_token_a)
            ).exists()
        )
        with self.assertRaises(AuthenticationFailed):
            resolve_api_session(raw_token_a, using="tenant_b")
        self.assertNotEqual(org_a.pk, org_b.pk)
        self.assertEqual(session_a._state.db, "default")


class CompanyEstablishmentHierarchyTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Tenant A",
            slug="tenant-a",
        )
        self.user = get_user_model().objects.create_user(
            username="scope.user",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        grant_organization_admin(user=self.user)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.company = Company.objects.create(
            organization=self.organization,
            name="Fashion Group BF",
            code="fashion-group-bf",
            legal_name="Fashion Group Burkina SARL",
            country_code="BF",
        )
        self.workshop = Establishment.objects.create(
            company=self.company,
            name="Atelier Central",
            code="atelier-central",
            site_type=Establishment.SiteType.WORKSHOP,
            city="Ouagadougou",
            country_code="BF",
        )
        self.store = Establishment.objects.create(
            company=self.company,
            name="Boutique Centre",
            code="boutique-centre",
            site_type=Establishment.SiteType.STORE,
            city="Ouagadougou",
            country_code="BF",
        )

    def test_company_belongs_to_local_organization(self):
        self.assertEqual(self.company.organization_id, self.organization.id)

    def test_organization_can_have_multiple_establishments(self):
        self.assertEqual(self.company.establishments.count(), 2)

    def test_establishment_organization_is_derived_from_company(self):
        self.assertEqual(self.workshop.organization_id, self.organization.id)
        self.assertEqual(self.store.organization_id, self.organization.id)

    def test_company_list_is_scoped_to_users_organization(self):
        response = self.client.get("/api/v1/companies/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            str(response.data["results"][0]["organization_id"]),
            str(self.organization.id),
        )

    def test_establishment_list_supports_company_scope_filter(self):
        response = self.client.get(
            f"/api/v1/establishments/?company_id={self.company.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        returned_ids = {
            str(item["id"]) for item in response.data["results"]
        }
        self.assertEqual(
            returned_ids,
            {str(self.workshop.id), str(self.store.id)},
        )

    def test_unknown_company_is_not_disclosed(self):
        response = self.client.get(f"/api/v1/companies/{uuid.uuid4()}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_establishment_is_not_disclosed(self):
        response = self.client.get(
            f"/api/v1/establishments/{uuid.uuid4()}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@unittest.skipUnless(TENANT_B_AVAILABLE, "tenant_b database alias is not configured")
class CrossDatabaseHierarchyIsolationTests(TestCase):
    databases = {"default", "tenant_b"} if TENANT_B_AVAILABLE else {"default"}

    def test_establishment_cannot_reference_company_from_another_tenant_database(self):
        org_a = Organization.objects.using("default").create(
            name="Tenant A",
            slug="tenant-a",
        )
        org_b = Organization.objects.using("tenant_b").create(
            name="Tenant B",
            slug="tenant-b",
        )
        Company.objects.using("default").create(
            organization=org_a,
            name="Company A",
            code="company-a",
        )
        company_b = Company.objects.using("tenant_b").create(
            organization=org_b,
            name="Company B",
            code="company-b",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic(using="default"):
                Establishment.objects.using("default").create(
                    company_id=company_b.id,
                    name="Invalid cross-tenant site",
                    code="invalid-cross-tenant-site",
                    site_type=Establishment.SiteType.WORKSHOP,
                )
