from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.generators import SchemaGenerator
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.audit.models import AuditEvent
from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.customers.models import Customer
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import Currency
from ivadoo.organizations.models import Company, Establishment, Organization

from .models import (
    CRMConversionEvent,
    CRMLead,
    CRMOpportunity,
    CRMPipelineStage,
    CRMSource,
)


class CRMApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="CRM Org", slug="crm-org")
        self.currency, _ = Currency.objects.update_or_create(
            code="XOF",
            defaults={
                "name": "West African CFA franc",
                "symbol": "FCFA",
                "decimal_places": 0,
                "rounding": Decimal("1"),
                "is_active": True,
            },
        )
        self.company = Company.objects.create(
            organization=self.organization,
            name="CRM Company",
            code="crm-company",
            functional_currency=self.currency,
        )
        self.establishment = Establishment.objects.create(
            company=self.company,
            name="Ouaga Store",
            code="ouaga-store",
            site_type=Establishment.SiteType.STORE,
            timezone="UTC",
        )
        self.user = User.objects.create_user(
            username="crm.manager",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        self.role = Role.objects.create(
            organization=self.organization,
            code="crm-manager",
            name="CRM manager",
            is_active=True,
        )
        self.role.permissions.set(
            Permission.objects.filter(
                code__in=(
                    "enterprise.crm.view",
                    "enterprise.crm.manage",
                    "enterprise.crm.convert",
                )
            )
        )
        AccessGrant.objects.create(user=self.user, role=self.role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.source = CRMSource.objects.create(
            organization=self.organization,
            company=self.company,
            code="instagram",
            name="Instagram",
            source_type=CRMSource.SourceType.SOCIAL,
        )
        self.stage_new = CRMPipelineStage.objects.create(
            organization=self.organization,
            company=self.company,
            code="new",
            name="New",
            position=10,
            probability=Decimal("10"),
        )
        self.stage_won = CRMPipelineStage.objects.create(
            organization=self.organization,
            company=self.company,
            code="won",
            name="Won",
            position=90,
            stage_type=CRMPipelineStage.StageType.WON,
            probability=Decimal("100"),
        )

    def _create_lead(self, **overrides):
        payload = {
            "company_id": str(self.company.id),
            "establishment_id": str(self.establishment.id),
            "source_id": str(self.source.id),
            "owner_id": str(self.user.id),
            "code": "LEAD-001",
            "prospect_type": "individual",
            "display_name": "Awa Kaboré",
            "first_name": "Awa",
            "last_name": "Kaboré",
            "email": "awa@example.com",
            "phone": "+22670000001",
            "language_code": "fr",
            "notes": "Instagram enquiry",
        }
        payload.update(overrides)
        return self.client.post("/api/v1/crm/leads/", payload, format="json")

    def test_sources_stages_leads_and_opportunities_are_exposed(self):
        source_response = self.client.post(
            "/api/v1/crm/sources/",
            {
                "company_id": str(self.company.id),
                "code": "referral",
                "name": "Referral",
                "source_type": "referral",
            },
            format="json",
        )
        self.assertEqual(source_response.status_code, status.HTTP_201_CREATED, source_response.data)

        stage_response = self.client.post(
            "/api/v1/crm/stages/",
            {
                "company_id": str(self.company.id),
                "code": "qualified",
                "name": "Qualified",
                "position": 20,
                "stage_type": "open",
                "probability": "40.00",
            },
            format="json",
        )
        self.assertEqual(stage_response.status_code, status.HTTP_201_CREATED, stage_response.data)

        lead_response = self._create_lead()
        self.assertEqual(lead_response.status_code, status.HTTP_201_CREATED, lead_response.data)

        opportunity_response = self.client.post(
            "/api/v1/crm/opportunities/",
            {
                "company_id": str(self.company.id),
                "lead_id": lead_response.data["id"],
                "stage_id": str(self.stage_new.id),
                "code": "OPP-001",
                "title": "Wedding collection",
                "expected_revenue": "150000.00",
            },
            format="json",
        )
        self.assertEqual(
            opportunity_response.status_code,
            status.HTTP_201_CREATED,
            opportunity_response.data,
        )
        self.assertEqual(
            Decimal(opportunity_response.data["probability"]), Decimal("10.00")
        )
        self.assertEqual(opportunity_response.data["source_id"], str(self.source.id))
        self.assertEqual(opportunity_response.data["owner_id"], str(self.user.id))

    def test_lead_conversion_creates_customer_once_and_is_idempotent(self):
        lead_response = self._create_lead()
        self.assertEqual(lead_response.status_code, status.HTTP_201_CREATED, lead_response.data)
        lead_id = lead_response.data["id"]

        converted = self.client.post(
            f"/api/v1/crm/leads/{lead_id}/actions/convert/",
            {"customer_code": "CUS-AWA"},
            format="json",
        )
        self.assertEqual(converted.status_code, status.HTTP_200_OK, converted.data)
        self.assertTrue(converted.data["created_customer"])
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(CRMConversionEvent.objects.filter(lead_id=lead_id).count(), 1)

        lead = CRMLead.objects.get(id=lead_id)
        self.assertEqual(lead.status, CRMLead.Status.CONVERTED)
        self.assertEqual(str(lead.converted_customer_id), converted.data["customer_id"])

        repeated = self.client.post(
            f"/api/v1/crm/leads/{lead_id}/actions/convert/",
            {"customer_code": "IGNORED-BECAUSE-IDEMPOTENT"},
            format="json",
        )
        self.assertEqual(repeated.status_code, status.HTTP_200_OK, repeated.data)
        self.assertEqual(repeated.data["id"], converted.data["id"])
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(CRMConversionEvent.objects.filter(lead_id=lead_id).count(), 1)

    def test_existing_matching_customer_is_reused_without_duplicate(self):
        existing = Customer.objects.create(
            organization=self.organization,
            company=self.company,
            establishment=self.establishment,
            code="CUS-EXISTING",
            display_name="Awa Existing",
            first_name="Awa",
            email="awa@example.com",
            phone="+22679999999",
            preferred_currency=self.currency,
        )
        lead_response = self._create_lead(phone="+22670000002")
        self.assertEqual(lead_response.status_code, status.HTTP_201_CREATED, lead_response.data)

        converted = self.client.post(
            f"/api/v1/crm/leads/{lead_response.data['id']}/actions/convert/",
            {},
            format="json",
        )
        self.assertEqual(converted.status_code, status.HTTP_200_OK, converted.data)
        self.assertFalse(converted.data["created_customer"])
        self.assertEqual(converted.data["customer_id"], str(existing.id))
        self.assertEqual(Customer.objects.count(), 1)

    def test_ambiguous_customer_match_requires_explicit_customer(self):
        Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="CUS-1",
            display_name="Awa One",
            email="shared@example.com",
        )
        Customer.objects.create(
            organization=self.organization,
            company=self.company,
            code="CUS-2",
            display_name="Awa Two",
            email="shared@example.com",
        )
        lead_response = self._create_lead(
            code="LEAD-AMBIGUOUS",
            email="shared@example.com",
            phone="",
        )
        self.assertEqual(lead_response.status_code, status.HTTP_201_CREATED, lead_response.data)

        converted = self.client.post(
            f"/api/v1/crm/leads/{lead_response.data['id']}/actions/convert/",
            {"customer_code": "CUS-NEW"},
            format="json",
        )
        self.assertEqual(converted.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Customer.objects.count(), 2)
        self.assertEqual(CRMConversionEvent.objects.count(), 0)

    def test_linked_opportunity_and_lead_converge_on_same_customer(self):
        lead_response = self._create_lead(code="LEAD-OPP", email="opp@example.com")
        self.assertEqual(lead_response.status_code, status.HTTP_201_CREATED, lead_response.data)

        opportunity = self.client.post(
            "/api/v1/crm/opportunities/",
            {
                "company_id": str(self.company.id),
                "lead_id": lead_response.data["id"],
                "stage_id": str(self.stage_won.id),
                "code": "OPP-CONVERT",
                "title": "Corporate uniforms",
                "expected_revenue": "500000.00",
            },
            format="json",
        )
        self.assertEqual(opportunity.status_code, status.HTTP_201_CREATED, opportunity.data)

        converted = self.client.post(
            f"/api/v1/crm/opportunities/{opportunity.data['id']}/actions/convert/",
            {"customer_code": "CUS-OPP"},
            format="json",
        )
        self.assertEqual(converted.status_code, status.HTTP_200_OK, converted.data)

        lead = CRMLead.objects.get(id=lead_response.data["id"])
        opp = CRMOpportunity.objects.get(id=opportunity.data["id"])
        self.assertEqual(lead.converted_customer_id, opp.customer_id)
        self.assertEqual(str(opp.customer_id), converted.data["customer_id"])
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(CRMConversionEvent.objects.count(), 2)
        self.assertTrue(CRMConversionEvent.objects.filter(lead=lead).exists())
        self.assertTrue(CRMConversionEvent.objects.filter(opportunity=opp).exists())

    def test_direct_opportunity_can_convert_without_lead(self):
        opportunity = self.client.post(
            "/api/v1/crm/opportunities/",
            {
                "company_id": str(self.company.id),
                "establishment_id": str(self.establishment.id),
                "source_id": str(self.source.id),
                "stage_id": str(self.stage_new.id),
                "owner_id": str(self.user.id),
                "code": "OPP-DIRECT",
                "title": "Boutique wholesale prospect",
                "prospect_type": "company",
                "contact_name": "Maison Faso",
                "legal_name": "Maison Faso SARL",
                "email": "contact@maisonfaso.example",
                "phone": "+22670000003",
                "expected_revenue": "750000.00",
            },
            format="json",
        )
        self.assertEqual(opportunity.status_code, status.HTTP_201_CREATED, opportunity.data)

        converted = self.client.post(
            f"/api/v1/crm/opportunities/{opportunity.data['id']}/actions/convert/",
            {"customer_code": "CUS-MAISON-FASO"},
            format="json",
        )
        self.assertEqual(converted.status_code, status.HTTP_200_OK, converted.data)
        customer = Customer.objects.get(id=converted.data["customer_id"])
        self.assertEqual(customer.customer_type, Customer.CustomerType.COMPANY)
        self.assertEqual(customer.legal_name, "Maison Faso SARL")
        self.assertEqual(customer.preferred_currency_id, "XOF")

    def test_disqualified_lead_cannot_be_converted(self):
        lead_response = self._create_lead(
            code="LEAD-DISQ",
            status=CRMLead.Status.DISQUALIFIED,
            email="disqualified@example.com",
        )
        self.assertEqual(lead_response.status_code, status.HTTP_201_CREATED, lead_response.data)

        converted = self.client.post(
            f"/api/v1/crm/leads/{lead_response.data['id']}/actions/convert/",
            {"customer_code": "CUS-DISQ"},
            format="json",
        )
        self.assertEqual(converted.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Customer.objects.count(), 0)

    def test_lead_cannot_be_marked_converted_by_direct_patch(self):
        lead_response = self._create_lead(code="LEAD-PATCH", email="patch@example.com")
        self.assertEqual(lead_response.status_code, status.HTTP_201_CREATED, lead_response.data)

        patched = self.client.patch(
            f"/api/v1/crm/leads/{lead_response.data['id']}/",
            {"status": CRMLead.Status.CONVERTED},
            format="json",
        )
        self.assertEqual(patched.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            CRMLead.objects.get(id=lead_response.data["id"]).status,
            CRMLead.Status.NEW,
        )

    def test_company_scope_prevents_cross_company_crm_access(self):
        other_company = Company.objects.create(
            organization=self.organization,
            name="Other CRM Company",
            code="other-crm-company",
            functional_currency=self.currency,
        )
        other_lead = CRMLead.objects.create(
            organization=self.organization,
            company=other_company,
            code="OTHER-LEAD",
            display_name="Other Prospect",
            email="other@example.com",
            created_by=self.user,
        )
        response = self.client.post(
            f"/api/v1/crm/leads/{other_lead.id}/actions/convert/",
            {"customer_code": "CUS-OTHER"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Customer.objects.count(), 0)

        listing = self.client.get("/api/v1/crm/leads/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK, listing.data)
        result_ids = {item["id"] for item in listing.data["results"]}
        self.assertNotIn(str(other_lead.id), result_ids)

    def test_conversion_history_is_immutable_and_audited(self):
        lead_response = self._create_lead(code="LEAD-AUDIT", email="audit@example.com")
        converted = self.client.post(
            f"/api/v1/crm/leads/{lead_response.data['id']}/actions/convert/",
            {"customer_code": "CUS-AUDIT"},
            format="json",
        )
        self.assertEqual(converted.status_code, status.HTTP_200_OK, converted.data)
        event = CRMConversionEvent.objects.get(id=converted.data["id"])

        event.created_customer = False
        with self.assertRaises(DjangoValidationError):
            event.save()
        with self.assertRaises(DjangoValidationError):
            event.delete()

        audit = AuditEvent.objects.filter(
            action="enterprise.crm.convert",
            object_id=str(event.id),
        ).get()
        self.assertEqual(audit.company_id, self.company.id)
        self.assertEqual(audit.establishment_id, self.establishment.id)
        self.assertEqual(audit.after["customer_id"], str(event.customer_id))
        self.assertEqual(audit.metadata["source_kind"], "lead")

    def test_crm_routes_are_declared_in_openapi(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        paths = schema["paths"]
        expected = {
            "/api/v1/crm/sources/",
            "/api/v1/crm/sources/{source_id}/",
            "/api/v1/crm/stages/",
            "/api/v1/crm/stages/{stage_id}/",
            "/api/v1/crm/leads/",
            "/api/v1/crm/leads/{lead_id}/",
            "/api/v1/crm/leads/{lead_id}/actions/convert/",
            "/api/v1/crm/opportunities/",
            "/api/v1/crm/opportunities/{opportunity_id}/",
            "/api/v1/crm/opportunities/{opportunity_id}/actions/convert/",
            "/api/v1/crm/conversions/",
        }
        self.assertEqual(expected.difference(paths), set())
