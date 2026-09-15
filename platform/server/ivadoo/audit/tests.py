from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DatabaseError, transaction
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.authorization.models import AccessGrant, Permission, Role
from ivadoo.authorization.services import grant_organization_admin
from ivadoo.identity.services import create_api_session
from ivadoo.organizations.models import Company, Establishment, Organization

from .models import AuditEvent
from .services import record_audit_event


class AuditJournalTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Tenant A",
            slug="tenant-a",
        )
        self.user = get_user_model().objects.create_user(
            username="audit.admin",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )
        grant_organization_admin(user=self.user)
        _, token = create_api_session(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_authorized_admin_can_read_and_filter_audit_events(self):
        record_audit_event(
            organization=self.organization,
            actor=self.user,
            action="test.visible",
            object_type="test.object",
            object_id="visible",
        )
        record_audit_event(
            organization=self.organization,
            actor=self.user,
            action="test.other",
            object_type="test.object",
            object_id="other",
        )

        response = self.client.get(
            "/api/v1/audit/events/?action=test.visible"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["action"],
            "test.visible",
        )

    def test_audit_api_is_read_only(self):
        response = self.client.post(
            "/api/v1/audit/events/",
            {"action": "forged.event"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertFalse(
            AuditEvent.objects.filter(action="forged.event").exists()
        )

    def test_company_create_records_actor_scope_and_after_value(self):
        response = self.client.post(
            "/api/v1/companies/",
            {
                "name": "Fashion Group BF",
                "code": "fashion-group-bf",
                "country_code": "BF",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = AuditEvent.objects.get(action="foundation.company.create")
        self.assertEqual(event.actor_id, self.user.id)
        self.assertEqual(event.organization_id, self.organization.id)
        self.assertEqual(str(event.company_id), response.data["id"])
        self.assertIsNone(event.before)
        self.assertEqual(event.after["name"], "Fashion Group BF")
        self.assertNotIn("password", event.after)

    def test_company_update_records_old_and_new_values(self):
        company = Company.objects.create(
            organization=self.organization,
            name="Old Name",
            code="company-a",
        )

        response = self.client.patch(
            f"/api/v1/companies/{company.id}/",
            {"name": "New Name"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event = AuditEvent.objects.get(action="foundation.company.update")
        self.assertEqual(event.before["name"], "Old Name")
        self.assertEqual(event.after["name"], "New Name")
        self.assertEqual(event.company_id, company.id)

    def test_establishment_create_records_company_and_establishment_scope(self):
        company = Company.objects.create(
            organization=self.organization,
            name="Company A",
            code="company-a",
        )

        response = self.client.post(
            "/api/v1/establishments/",
            {
                "company_id": str(company.id),
                "name": "Atelier Central",
                "code": "atelier-central",
                "site_type": "workshop",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = AuditEvent.objects.get(
            action="foundation.establishment.create"
        )
        self.assertEqual(event.company_id, company.id)
        self.assertEqual(str(event.establishment_id), response.data["id"])

    def test_access_changes_are_audited_without_password_values(self):
        created_user = self.client.post(
            "/api/v1/access/users/",
            {
                "login": "managed.user",
                "password": "Managed-Strong-Password-42!",
                "email": "managed@example.test",
            },
            format="json",
        )
        self.assertEqual(created_user.status_code, status.HTTP_201_CREATED)

        created_role = self.client.post(
            "/api/v1/access/roles/",
            {
                "code": "company-reader",
                "name": "Company reader",
                "permission_codes": ["foundation.company.view"],
            },
            format="json",
        )
        self.assertEqual(created_role.status_code, status.HTTP_201_CREATED)

        user_event = AuditEvent.objects.get(action="access.user.create")
        role_event = AuditEvent.objects.get(action="access.role.create")
        self.assertNotIn("password", user_event.after)
        self.assertEqual(user_event.after["username"], "managed.user")
        self.assertEqual(
            role_event.after["permission_codes"],
            ["foundation.company.view"],
        )

    def test_grant_revoke_records_before_and_after(self):
        company = Company.objects.create(
            organization=self.organization,
            name="Company A",
            code="company-a",
        )
        role = Role.objects.create(
            organization=self.organization,
            code="reader",
            name="Reader",
        )
        role.permissions.add(
            Permission.objects.get(code="foundation.company.view")
        )
        target_user = get_user_model().objects.create_user(
            username="target.user",
            password="Target-Strong-Password-42!",
            organization=self.organization,
        )
        grant = AccessGrant.objects.create(
            user=target_user,
            role=role,
            company=company,
        )

        response = self.client.post(
            f"/api/v1/access/grants/{grant.id}/revoke/"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        event = AuditEvent.objects.get(action="access.grant.revoke")
        self.assertIsNone(event.before["revoked_at"])
        self.assertIsNotNone(event.after["revoked_at"])
        self.assertEqual(event.company_id, company.id)

    def test_user_without_audit_permission_cannot_read_journal(self):
        limited_user = get_user_model().objects.create_user(
            username="limited.user",
            password="Limited-Strong-Password-42!",
            organization=self.organization,
        )
        _, token = create_api_session(user=limited_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/v1/audit/events/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_model_update_and_delete_are_rejected(self):
        event = record_audit_event(
            organization=self.organization,
            actor=self.user,
            action="test.immutable",
            object_type="test.object",
            object_id="one",
        )

        event.action = "test.changed"
        with self.assertRaises(TypeError):
            event.save()
        with self.assertRaises(TypeError):
            event.delete()

    def test_postgresql_trigger_rejects_queryset_update_and_delete(self):
        event = record_audit_event(
            organization=self.organization,
            actor=self.user,
            action="test.database_immutable",
            object_type="test.object",
            object_id="two",
        )

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                AuditEvent.objects.filter(pk=event.pk).update(
                    action="test.changed"
                )

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                AuditEvent.objects.filter(pk=event.pk).delete()

        event.refresh_from_db()
        self.assertEqual(event.action, "test.database_immutable")


class AuthenticationAuditTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.organization = Organization.objects.create(
            name="Tenant A",
            slug="tenant-a",
        )
        self.user = get_user_model().objects.create_user(
            username="login.user",
            password="Strong-Test-Password-42!",
            organization=self.organization,
        )

    def test_failed_login_is_audited_without_password(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {
                "login": "login.user",
                "password": "wrong-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        event = AuditEvent.objects.get(
            action="auth.login",
            result=AuditEvent.Result.FAILURE,
        )
        self.assertEqual(event.object_label, "login.user")
        self.assertEqual(event.metadata["reason"], "invalid_credentials")
        self.assertNotIn("password", event.metadata)

    def test_login_and_logout_are_audited_without_token_material(self):
        login = self.client.post(
            "/api/v1/auth/login/",
            {
                "login": "login.user",
                "password": "Strong-Test-Password-42!",
                "device_id": "device-1",
            },
            format="json",
        )

        self.assertEqual(login.status_code, status.HTTP_200_OK)
        login_event = AuditEvent.objects.get(action="auth.login")
        self.assertEqual(login_event.actor_id, self.user.id)
        self.assertNotIn("token", login_event.after)
        self.assertNotIn("token_digest", login_event.after)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['token']}"
        )
        logout = self.client.post("/api/v1/auth/logout/")
        self.assertEqual(logout.status_code, status.HTTP_204_NO_CONTENT)

        logout_event = AuditEvent.objects.get(action="auth.logout")
        self.assertIsNone(logout_event.before["revoked_at"])
        self.assertIsNotNone(logout_event.after["revoked_at"])
        self.assertNotIn("token_digest", logout_event.after)
