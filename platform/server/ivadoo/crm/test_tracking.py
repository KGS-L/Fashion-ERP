from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.audit.models import AuditEvent
from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.identity.models import User
from ivadoo.identity.services import create_api_session
from ivadoo.internationalization.models import Currency
from ivadoo.organizations.models import Company, Establishment, Organization

from .models import CRMLead, CRMPipelineStage, CRMSource


class CRMTrackingApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Tracking Org", slug="tracking-org")
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
            name="Tracking Company",
            code="tracking-company",
            functional_currency=self.currency,
        )
        self.establishment = Establishment.objects.create(
            company=self.company,
            name="Ouaga Boutique",
            code="ouaga-boutique",
            site_type=Establishment.SiteType.STORE,
            timezone="UTC",
        )
        self.user = User.objects.create_user(
            username="tracking.manager",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        role = Role.objects.create(
            organization=self.organization,
            code="tracking-manager",
            name="Tracking manager",
            is_active=True,
        )
        role.permissions.set(
            Permission.objects.filter(
                code__in=("enterprise.crm.view", "enterprise.crm.manage", "enterprise.crm.convert")
            )
        )
        AccessGrant.objects.create(user=self.user, role=role, company=self.company)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        self.source = CRMSource.objects.create(
            organization=self.organization,
            company=self.company,
            code="referral",
            name="Referral",
            source_type=CRMSource.SourceType.REFERRAL,
        )
        self.stage = CRMPipelineStage.objects.create(
            organization=self.organization,
            company=self.company,
            code="new",
            name="New",
            position=10,
            probability=Decimal("10"),
        )

    def _create_lead(self, code="LEAD-TRACK-001", email="track@example.com"):
        response = self.client.post(
            "/api/v1/crm/leads/",
            {
                "company_id": str(self.company.id),
                "establishment_id": str(self.establishment.id),
                "source_id": str(self.source.id),
                "owner_id": str(self.user.id),
                "code": code,
                "prospect_type": "individual",
                "display_name": "Awa Tracking",
                "first_name": "Awa",
                "last_name": "Tracking",
                "email": email,
                "phone": "+22670001001",
                "language_code": "fr",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response

    def test_followup_defaults_to_commercial_owner_and_supports_portfolio_filters(self):
        lead = self._create_lead()
        response = self.client.post(
            "/api/v1/crm/followups/",
            {
                "company_id": str(self.company.id),
                "establishment_id": str(self.establishment.id),
                "lead_id": lead.data["id"],
                "subject": "Fitting reminder",
                "description": "Call before the fitting appointment",
                "due_at": (timezone.now() + timedelta(days=1)).isoformat(),
                "priority": "high",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["assignee_id"], str(self.user.id))

        listed = self.client.get(
            "/api/v1/crm/followups/",
            {"assignee_id": str(self.user.id), "status": "planned", "search": "Fitting"},
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK, listed.data)
        self.assertEqual(listed.data["count"], 1)
        self.assertEqual(listed.data["results"][0]["id"], response.data["id"])

        completed = self.client.patch(
            f"/api/v1/crm/followups/{response.data['id']}/",
            {"status": "completed"},
            format="json",
        )
        self.assertEqual(completed.status_code, status.HTTP_200_OK, completed.data)
        self.assertIsNotNone(completed.data["completed_at"])

    def test_segment_and_interaction_history_follow_converted_customer(self):
        lead = self._create_lead()
        segment = self.client.post(
            "/api/v1/crm/segments/",
            {
                "company_id": str(self.company.id),
                "code": "vip-prospect",
                "name": "VIP prospect",
            },
            format="json",
        )
        self.assertEqual(segment.status_code, status.HTTP_201_CREATED, segment.data)
        membership = self.client.post(
            "/api/v1/crm/segment-memberships/",
            {"segment_id": segment.data["id"], "lead_id": lead.data["id"]},
            format="json",
        )
        self.assertEqual(membership.status_code, status.HTTP_201_CREATED, membership.data)

        interaction = self.client.post(
            "/api/v1/crm/interactions/",
            {
                "company_id": str(self.company.id),
                "establishment_id": str(self.establishment.id),
                "lead_id": lead.data["id"],
                "interaction_type": "call",
                "channel": "phone",
                "direction": "outbound",
                "subject": "Qualification call",
                "summary": "Customer confirmed the project and preferred delivery date.",
            },
            format="json",
        )
        self.assertEqual(interaction.status_code, status.HTTP_201_CREATED, interaction.data)

        converted = self.client.post(
            f"/api/v1/crm/leads/{lead.data['id']}/actions/convert/",
            {"customer_code": "CUS-TRACK-001"},
            format="json",
        )
        self.assertEqual(converted.status_code, status.HTTP_200_OK, converted.data)
        customer_id = converted.data["customer_id"]

        memberships = self.client.get(
            "/api/v1/crm/segment-memberships/", {"customer_id": customer_id}
        )
        self.assertEqual(memberships.status_code, status.HTTP_200_OK, memberships.data)
        self.assertEqual(memberships.data["count"], 1)
        self.assertEqual(memberships.data["results"][0]["id"], membership.data["id"])

        interactions = self.client.get(
            "/api/v1/crm/interactions/", {"customer_id": customer_id}
        )
        self.assertEqual(interactions.status_code, status.HTTP_200_OK, interactions.data)
        self.assertEqual(interactions.data["count"], 1)
        self.assertEqual(interactions.data["results"][0]["id"], interaction.data["id"])

    def test_lead_status_changes_remain_in_immutable_audit_history(self):
        lead = self._create_lead()
        changed = self.client.patch(
            f"/api/v1/crm/leads/{lead.data['id']}/",
            {"status": "qualified"},
            format="json",
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK, changed.data)
        event = AuditEvent.objects.filter(
            action="enterprise.crm.lead.update",
            object_type="crm.crmlead",
            object_id=str(lead.data["id"]),
        ).latest("occurred_at")
        self.assertEqual(event.before["status"], CRMLead.Status.NEW)
        self.assertEqual(event.after["status"], CRMLead.Status.QUALIFIED)

    def test_tracking_write_is_denied_outside_granted_company_scope(self):
        other_company = Company.objects.create(
            organization=self.organization,
            name="Other Company",
            code="other-company",
            functional_currency=self.currency,
        )
        response = self.client.post(
            "/api/v1/crm/segments/",
            {"company_id": str(other_company.id), "code": "blocked", "name": "Blocked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)
