from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from fashionerp.identity.services import create_api_session
from fashionerp.organizations.models import Company, Establishment, Organization

from .models import AccessGrant, AccessGroup, Permission, Role
from .services import (
    ensure_foundation_permission_catalog,
    grant_organization_admin,
    has_permission,
)


class ScopedRbacTests(APITestCase):
    def setUp(self):
        ensure_foundation_permission_catalog()
        self.organization = Organization.objects.create(
            name="Tenant A",
            slug="tenant-a",
        )
        self.company_a = Company.objects.create(
            organization=self.organization,
            name="Company A",
            code="company-a",
        )
        self.company_b = Company.objects.create(
            organization=self.organization,
            name="Company B",
            code="company-b",
        )
        self.site_a1 = Establishment.objects.create(
            company=self.company_a,
            name="Workshop A1",
            code="workshop-a1",
            site_type=Establishment.SiteType.WORKSHOP,
        )
        self.site_a2 = Establishment.objects.create(
            company=self.company_a,
            name="Store A2",
            code="store-a2",
            site_type=Establishment.SiteType.STORE,
        )
        self.site_b1 = Establishment.objects.create(
            company=self.company_b,
            name="Warehouse B1",
            code="warehouse-b1",
            site_type=Establishment.SiteType.WAREHOUSE,
        )
        self.user = get_user_model().objects.create_user(
            username="scoped.user",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.company_reader = Role.objects.create(
            organization=self.organization,
            code="company-reader",
            name="Company reader",
        )
        self.company_reader.permissions.add(
            Permission.objects.get(code="foundation.company.view"),
            Permission.objects.get(code="foundation.establishment.view"),
        )

    def test_authenticated_user_without_grant_is_denied_by_default(self):
        companies = self.client.get("/api/v1/companies/")
        establishments = self.client.get("/api/v1/establishments/")

        self.assertEqual(companies.status_code, status.HTTP_200_OK)
        self.assertEqual(companies.data["count"], 0)
        self.assertEqual(establishments.status_code, status.HTTP_200_OK)
        self.assertEqual(establishments.data["count"], 0)

    def test_company_scoped_grant_limits_company_and_establishment_lists(self):
        AccessGrant.objects.create(
            user=self.user,
            role=self.company_reader,
            company=self.company_a,
        )

        companies = self.client.get("/api/v1/companies/")
        establishments = self.client.get("/api/v1/establishments/")

        self.assertEqual(companies.data["count"], 1)
        self.assertEqual(
            str(companies.data["results"][0]["id"]),
            str(self.company_a.id),
        )
        returned_sites = {
            str(item["id"]) for item in establishments.data["results"]
        }
        self.assertEqual(
            returned_sites,
            {str(self.site_a1.id), str(self.site_a2.id)},
        )
        self.assertNotIn(str(self.site_b1.id), returned_sites)

    def test_establishment_scoped_grant_only_exposes_that_site(self):
        AccessGrant.objects.create(
            user=self.user,
            role=self.company_reader,
            establishment=self.site_a1,
        )

        establishments = self.client.get("/api/v1/establishments/")

        self.assertEqual(establishments.data["count"], 1)
        self.assertEqual(
            str(establishments.data["results"][0]["id"]),
            str(self.site_a1.id),
        )

    def test_group_grant_is_effective(self):
        group = AccessGroup.objects.create(
            organization=self.organization,
            code="workshop-team",
            name="Workshop team",
        )
        group.members.add(self.user)
        AccessGrant.objects.create(
            group=group,
            role=self.company_reader,
            company=self.company_a,
        )

        self.assertTrue(
            has_permission(
                self.user,
                "foundation.establishment.view",
                establishment=self.site_a1,
            )
        )

    def test_revoked_grant_takes_effect_on_next_request(self):
        grant = AccessGrant.objects.create(
            user=self.user,
            role=self.company_reader,
            company=self.company_a,
        )
        allowed = self.client.get(f"/api/v1/companies/{self.company_a.id}/")
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

        grant.revoke()

        denied = self.client.get(f"/api/v1/companies/{self.company_a.id}/")
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_permission_removal_takes_effect_on_next_request(self):
        AccessGrant.objects.create(
            user=self.user,
            role=self.company_reader,
            company=self.company_a,
        )
        allowed = self.client.get(f"/api/v1/companies/{self.company_a.id}/")
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

        self.company_reader.permissions.remove(
            Permission.objects.get(code="foundation.company.view")
        )

        denied = self.client.get(f"/api/v1/companies/{self.company_a.id}/")
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_company_scope_does_not_allow_other_company_update(self):
        manager = Role.objects.create(
            organization=self.organization,
            code="company-manager",
            name="Company manager",
        )
        manager.permissions.add(
            Permission.objects.get(code="foundation.company.manage")
        )
        AccessGrant.objects.create(
            user=self.user,
            role=manager,
            company=self.company_a,
        )

        allowed = self.client.patch(
            f"/api/v1/companies/{self.company_a.id}/",
            {"name": "Company A updated"},
            format="json",
        )
        denied = self.client.patch(
            f"/api/v1/companies/{self.company_b.id}/",
            {"name": "Company B leaked"},
            format="json",
        )

        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)
        self.company_b.refresh_from_db()
        self.assertEqual(self.company_b.name, "Company B")

    def test_access_administration_requires_organization_scope_permission(self):
        denied = self.client.get("/api/v1/access/roles/")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        grant_organization_admin(user=self.user)

        allowed = self.client.get("/api/v1/access/roles/")
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_bootstrap_admin_full_access_covers_foundation_permissions(self):
        grant_organization_admin(user=self.user)

        self.assertTrue(
            has_permission(
                self.user,
                "foundation.company.manage",
                company=self.company_b,
            )
        )
        self.assertTrue(
            has_permission(
                self.user,
                "foundation.establishment.manage",
                establishment=self.site_b1,
            )
        )
        self.assertTrue(
            has_permission(self.user, "foundation.access.manage")
        )
