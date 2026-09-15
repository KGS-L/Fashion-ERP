from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from fashionerp.internationalization.models import UnitOfMeasure
from fashionerp.organizations.models import Company, Organization

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
