from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.test import APITestCase

from fashionerp.audit.models import AuditEvent
from fashionerp.authorization.services import grant_organization_admin
from fashionerp.identity.services import create_api_session
from fashionerp.organizations.models import Company, Establishment, Organization

from .constants import SUPPORTED_LANGUAGE_CODES
from .models import Currency, ExchangeRate, UnitOfMeasure
from .services import (
    format_date,
    format_number,
    locale_formats,
    translate_key,
)


class InternationalizationServiceTests(APITestCase):
    def test_missing_translation_key_falls_back_to_key(self):
        self.assertEqual(
            translate_key(
                "foundation.missing.key",
                language_code="es",
            ),
            "foundation.missing.key",
        )

    def test_plural_catalog_supports_standard_and_arabic_forms(self):
        self.assertEqual(
            translate_key(
                "foundation.company.count",
                language_code="en",
                count=1,
            ),
            "1 company",
        )
        self.assertEqual(
            translate_key(
                "foundation.company.count",
                language_code="en",
                count=2,
            ),
            "2 companies",
        )
        self.assertEqual(
            translate_key(
                "foundation.company.count",
                language_code="ar",
                count=2,
            ),
            "شركتان",
        )

    def test_date_and_number_formats_follow_language(self):
        value = Decimal("1234.50")
        fr_number = format_number(
            value,
            language_code="fr",
            decimal_places=2,
        )
        en_number = format_number(
            value,
            language_code="en",
            decimal_places=2,
        )
        fr_date = format_date(date(2026, 9, 14), language_code="fr")
        en_date = format_date(date(2026, 9, 14), language_code="en")

        self.assertNotEqual(fr_number, en_number)
        self.assertIn(
            locale_formats("fr")["decimal_separator"],
            fr_number,
        )
        self.assertIn(
            locale_formats("en")["decimal_separator"],
            en_number,
        )
        self.assertNotEqual(fr_date, en_date)


class InternationalizationApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Tenant A",
            slug="tenant-a",
        )
        self.user = get_user_model().objects.create_user(
            username="i18n.admin",
            password="Strong-Test-Password-42!",
            organization=self.organization,
            language_code="fr",
        )
        grant_organization_admin(user=self.user)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_currency(self, code, name, symbol):
        response = self.client.post(
            "/api/v1/i18n/currencies/",
            {
                "code": code,
                "name": name,
                "symbol": symbol,
                "decimal_places": 2,
                "rounding": "0.01",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Currency.objects.get(pk=code)

    def test_user_without_i18n_permission_cannot_manage_reference_data(self):
        limited_user = get_user_model().objects.create_user(
            username="i18n.limited",
            password="Limited-Strong-Password-42!",
            organization=self.organization,
        )
        _, token = create_api_session(user=limited_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post(
            "/api/v1/i18n/currencies/",
            {
                "code": "ZZZ",
                "name": "Blocked currency",
                "decimal_places": 2,
                "rounding": "0.01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Currency.objects.filter(pk="ZZZ").exists())

    def test_initial_language_set_and_arabic_direction(self):
        response = self.client.get("/api/v1/i18n/languages/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item["code"] for item in response.data},
            SUPPORTED_LANGUAGE_CODES,
        )
        arabic = next(
            item for item in response.data if item["code"] == "ar"
        )
        self.assertEqual(arabic["direction"], "rtl")

    def test_user_language_change_changes_default_catalog(self):
        update = self.client.patch(
            f"/api/v1/access/users/{self.user.id}/",
            {"language_code": "es"},
            format="json",
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)

        response = self.client.get("/api/v1/i18n/catalog/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["language"], "es")
        self.assertEqual(
            response.data["catalog"]["foundation.common.save"],
            "Guardar",
        )

    def test_company_currency_and_establishment_timezone_are_in_context(self):
        currency = self._create_currency("XTS", "Test currency", "T")
        company = Company.objects.create(
            organization=self.organization,
            name="Company A",
            code="company-a",
            language_code="pt",
            functional_currency=currency,
        )
        establishment = Establishment.objects.create(
            company=company,
            name="Atelier A",
            code="atelier-a",
            timezone="Africa/Ouagadougou",
        )

        response = self.client.get(
            "/api/v1/i18n/context/",
            {
                "company_id": str(company.id),
                "establishment_id": str(establishment.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["functional_currency"]["code"],
            "XTS",
        )
        self.assertEqual(
            response.data["timezone"],
            "Africa/Ouagadougou",
        )
        self.assertEqual(response.data["language"], "fr")

    def test_company_language_is_representable_independently(self):
        company = Company.objects.create(
            organization=self.organization,
            name="Company A",
            code="company-a",
            language_code="pt",
        )

        response = self.client.get(f"/api/v1/companies/{company.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["language_code"], "pt")

    def test_invalid_establishment_timezone_is_rejected(self):
        company = Company.objects.create(
            organization=self.organization,
            name="Company A",
            code="company-a",
        )

        response = self.client.post(
            "/api/v1/establishments/",
            {
                "company_id": str(company.id),
                "name": "Invalid timezone site",
                "code": "invalid-timezone-site",
                "timezone": "Mars/Olympus",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dated_exchange_rates_and_units_are_configurable_and_audited(self):
        base = self._create_currency("AAA", "Currency A", "A")
        quote = self._create_currency("BBB", "Currency B", "B")

        rate = self.client.post(
            "/api/v1/i18n/exchange-rates/",
            {
                "base_currency_code": base.code,
                "quote_currency_code": quote.code,
                "valid_on": "2026-09-14",
                "rate": "655.957000000000",
            },
            format="json",
        )
        self.assertEqual(rate.status_code, status.HTTP_201_CREATED)

        unit = self.client.post(
            "/api/v1/i18n/units/",
            {
                "code": "metre",
                "name": "Metre",
                "symbol": "m",
                "category": "length",
                "ratio_to_base": "1.000000000000",
                "rounding": "0.00100000",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(unit.status_code, status.HTTP_201_CREATED)

        self.assertTrue(
            ExchangeRate.objects.filter(
                organization=self.organization,
                valid_on=date(2026, 9, 14),
            ).exists()
        )
        self.assertTrue(
            UnitOfMeasure.objects.filter(
                organization=self.organization,
                code="metre",
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="i18n.exchange_rate.create"
            ).exists()
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="i18n.unit.create").exists()
        )

    def test_duplicate_dated_rate_is_rejected(self):
        base = self._create_currency("CCC", "Currency C", "C")
        quote = self._create_currency("DDD", "Currency D", "D")
        payload = {
            "base_currency_code": base.code,
            "quote_currency_code": quote.code,
            "valid_on": "2026-09-14",
            "rate": "1.250000000000",
        }

        first = self.client.post(
            "/api/v1/i18n/exchange-rates/",
            payload,
            format="json",
        )
        second = self.client.post(
            "/api/v1/i18n/exchange-rates/",
            payload,
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_timezone_validator_rejects_unknown_iana_zone(self):
        company = Company.objects.create(
            organization=self.organization,
            name="Company A",
            code="company-a",
        )
        establishment = Establishment(
            company=company,
            name="Invalid",
            code="invalid",
            timezone="Not/AZone",
        )

        with self.assertRaises(DjangoValidationError):
            establishment.full_clean()
