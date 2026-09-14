from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from fashionerp.authorization.models import AccessGrant
from fashionerp.internationalization.models import Currency, UnitOfMeasure

from .models import Company, Establishment, Organization


class FoundationReferenceDataTests(TestCase):
    databases = {"default", "tenant_b"}

    def test_pilot_profile_is_reproducible(self):
        call_command(
            "seed_foundation_reference",
            database="default",
            profile="pilot",
            verbosity=0,
        )
        call_command(
            "seed_foundation_reference",
            database="default",
            profile="pilot",
            verbosity=0,
        )

        organization = Organization.objects.get(slug="foundation-pilot")
        company = Company.objects.get(code="pilot-company")

        self.assertEqual(Organization.objects.count(), 1)
        self.assertEqual(Company.objects.count(), 1)
        self.assertEqual(company.organization_id, organization.id)
        self.assertEqual(company.establishments.count(), 2)
        self.assertEqual(get_user_model().objects.count(), 3)
        self.assertTrue(Currency.objects.filter(pk="XTS").exists())
        self.assertTrue(UnitOfMeasure.objects.filter(code="metre").exists())
        self.assertEqual(
            AccessGrant.objects.filter(revoked_at__isnull=True).count(),
            3,
        )

    def test_second_reference_organization_lives_in_isolated_database(self):
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

        self.assertEqual(
            Organization.objects.using("default").get().slug,
            "foundation-pilot",
        )
        self.assertEqual(
            Organization.objects.using("tenant_b").get().slug,
            "foundation-isolation",
        )
        self.assertFalse(
            Company.objects.using("default").filter(
                code="isolation-company"
            ).exists()
        )
        self.assertFalse(
            Company.objects.using("tenant_b").filter(
                code="pilot-company"
            ).exists()
        )
        self.assertEqual(
            Establishment.objects.using("tenant_b").count(),
            1,
        )
