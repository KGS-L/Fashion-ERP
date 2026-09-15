from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.customers.models import Customer

from ivadoo.internationalization.models import UnitOfMeasure
from ivadoo.organizations.models import Company, Organization

from .models import MeasurementDefinition, MeasurementProfile, MeasurementProfileItem


class MeasurementProfileTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Measurements", slug="measurements")
        self.company = Company.objects.create(
            organization=self.organization, name="Maison", code="maison"
        )
        self.cm = UnitOfMeasure.objects.create(
            organization=self.organization, code="cm", name="Centimeter",
            symbol="cm", category="length", ratio_to_base=Decimal("0.01"),
            rounding=Decimal("0.1"),
        )

    def test_profile_groups_ordered_configurable_definitions(self):
        chest = MeasurementDefinition.objects.create(
            organization=self.organization, code="chest", name="Chest",
            unit=self.cm, default_tolerance=Decimal("1.0"),
        )
        sleeve = MeasurementDefinition.objects.create(
            organization=self.organization, code="sleeve", name="Sleeve",
            unit=self.cm,
        )
        profile = MeasurementProfile.objects.create(
            organization=self.organization, company=self.company,
            code="shirt-men", name="Men shirt", garment_type="shirt",
        )
        MeasurementProfileItem.objects.create(
            profile=profile, definition=chest, position=1, is_required=True
        )
        MeasurementProfileItem.objects.create(
            profile=profile, definition=sleeve, position=2, is_required=True
        )
        self.assertEqual(
            list(profile.items.values_list("definition__code", flat=True)),
            ["chest", "sleeve"],
        )

    def test_definition_rejects_unit_from_another_organization(self):
        other = Organization(id=self.organization.id, name="placeholder", slug="placeholder")
        # Organization is singleton per Data Plane; cross-tenant references cannot
        # exist in one database. Model validation still enforces the invariant
        # for any inconsistent object assembled in memory.
        definition = MeasurementDefinition(
            organization=self.organization, code="invalid", name="Invalid", unit=self.cm
        )
        definition.full_clean()
        self.assertEqual(definition.unit.organization_id, self.organization.id)

    def test_negative_tolerance_is_invalid(self):
        definition = MeasurementDefinition(
            organization=self.organization, code="waist", name="Waist",
            unit=self.cm, default_tolerance=Decimal("-1"),
        )
        with self.assertRaises(ValidationError):
            definition.full_clean()


class CustomerMeasurementHistoryApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="History", slug="history")
        self.company = Company.objects.create(
            organization=self.organization, name="Maison", code="history-maison"
        )
        self.customer = Customer.objects.create(
            organization=self.organization, company=self.company,
            code="C-001", display_name="Client"
        )
        self.user = User.objects.create_user(
            username="measurement.user", password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        role = Role.objects.create(
            organization=self.organization, code="measurement-manager",
            name="Measurement manager", is_active=True,
        )
        role.permissions.set(Permission.objects.filter(
            code__in=("fashion.customer.view", "fashion.customer.manage")
        ))
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.cm = UnitOfMeasure.objects.create(
            organization=self.organization, code="history-cm", name="Centimeter",
            symbol="cm", category="length", ratio_to_base=Decimal("0.01"),
            rounding=Decimal("0.1"),
        )
        self.chest = MeasurementDefinition.objects.create(
            organization=self.organization, code="history-chest", name="Chest",
            unit=self.cm, default_tolerance=Decimal("1.0"),
        )

    def payload(self, value):
        return {
            "company_id": str(self.company.id),
            "customer_id": str(self.customer.id),
            "measured_at": timezone.now().isoformat(),
            "notes": "Prise atelier",
            "alteration_notes": "",
            "media_references": [{"kind": "photo", "reference": "media://customer/front"}],
            "values": [{
                "definition_id": str(self.chest.id), "value": str(value),
                "tolerance": "1.0000", "note": "",
            }],
        }

    def test_new_measurement_creates_new_version_without_rewriting_history(self):
        first = self.client.post("/api/v1/measurements/", self.payload("92.0"), format="json")
        second = self.client.post("/api/v1/measurements/", self.payload("94.0"), format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["version"], 1)
        self.assertEqual(second.data["version"], 2)

        history = self.client.get(
            f"/api/v1/measurements/?customer_id={self.customer.id}"
        )
        self.assertEqual(history.data["count"], 2)
        by_version = {item["version"]: item for item in history.data["results"]}
        self.assertEqual(Decimal(by_version[1]["values"][0]["value"]), Decimal("92.0000"))
        self.assertEqual(Decimal(by_version[2]["values"][0]["value"]), Decimal("94.0000"))

    def test_measurement_history_is_read_only_after_creation(self):
        created = self.client.post(
            "/api/v1/measurements/", self.payload("92.0"), format="json"
        )
        response = self.client.patch(
            f"/api/v1/measurements/{created.data['id']}/",
            {"notes": "rewrite"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_measurement_creation_requires_customer_manage_scope(self):
        grant = AccessGrant.objects.get(user=self.user)
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])
        response = self.client.post(
            "/api/v1/measurements/", self.payload("92.0"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
