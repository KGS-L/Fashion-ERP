import unittest
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from fashionerp.identity.models import ApiSession
from fashionerp.identity.services import create_api_session, digest_token

from .models import Organization
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
        session, self.token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_list_only_returns_authenticated_users_organization(self):
        response = self.client.get("/api/v1/organizations/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(str(response.data[0]["id"]), str(self.organization.id))

    def test_unknown_organization_uuid_returns_not_found(self):
        response = self.client.get(
            f"/api/v1/organizations/{uuid.uuid4()}/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "not_found")


class PhysicalDatabaseIsolationTests(TestCase):
    databases = {"default", "tenant_b"}

    @classmethod
    def setUpClass(cls):
        if "tenant_b" not in settings.DATABASES:
            raise unittest.SkipTest("tenant_b database alias is not configured")
        super().setUpClass()

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
        self.assertNotEqual(org_a.pk, org_b.pk)
        self.assertEqual(session_a._state.db, "default")
