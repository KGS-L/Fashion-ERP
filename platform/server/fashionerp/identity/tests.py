from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from fashionerp.organizations.models import Organization

from .models import ApiSession


class AuthenticationLifecycleTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="Test Organization",
            slug="test-organization",
        )
        self.user = get_user_model().objects.create_user(
            username="atelier.user",
            password="Strong-Test-Password-42!",
            email="atelier@example.test",
            organization=self.organization,
        )

    def login(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {
                "login": "atelier.user",
                "password": "Strong-Test-Password-42!",
                "device_id": "test-device",
                "device_label": "Test device",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response

    def authorize(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_unauthenticated_access_is_rejected(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.data["error"]["code"],
            "authentication_required",
        )

    def test_password_is_stored_with_argon2(self):
        self.assertEqual(identify_hasher(self.user.password).algorithm, "argon2")

    def test_raw_bearer_token_is_not_stored(self):
        response = self.login()
        raw_token = response.data["token"]
        session = ApiSession.objects.get(user=self.user)

        self.assertNotEqual(session.token_digest, raw_token)
        self.assertNotIn(raw_token, session.token_digest)

    def test_login_and_current_user(self):
        response = self.login()
        token = response.data["token"]
        self.authorize(token)

        me = self.client.get("/api/v1/auth/me/")

        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data["login"], "atelier.user")
        self.assertEqual(ApiSession.objects.filter(user=self.user).count(), 1)

    def test_logout_revokes_current_session(self):
        response = self.login()
        token = response.data["token"]
        self.authorize(token)

        logout = self.client.post("/api/v1/auth/logout/")
        self.assertEqual(logout.status_code, status.HTTP_204_NO_CONTENT)

        denied = self.client.get("/api/v1/auth/me/")
        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_session_is_rejected(self):
        response = self.login()
        token = response.data["token"]
        session = ApiSession.objects.get(user=self.user)
        session.expires_at = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=["expires_at"])

        self.authorize(token)
        denied = self.client.get("/api/v1/auth/me/")

        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_idle_expired_session_is_rejected(self):
        response = self.login()
        token = response.data["token"]
        session = ApiSession.objects.get(user=self.user)
        session.idle_expires_at = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=["idle_expires_at"])

        self.authorize(token)
        denied = self.client.get("/api/v1/auth/me/")

        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_session_is_rejected(self):
        response = self.login()
        token = response.data["token"]
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.authorize(token)
        denied = self.client.get("/api/v1/auth/me/")

        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_and_revoke_own_session(self):
        response = self.login()
        token = response.data["token"]
        session_id = response.data["session"]["id"]
        self.authorize(token)

        sessions = self.client.get("/api/v1/auth/sessions/")
        self.assertEqual(sessions.status_code, status.HTTP_200_OK)
        self.assertEqual(sessions.data["count"], 1)
        self.assertEqual(len(sessions.data["results"]), 1)

        revoked = self.client.post(
            f"/api/v1/auth/sessions/{session_id}/revoke/"
        )
        self.assertEqual(revoked.status_code, status.HTTP_204_NO_CONTENT)

        denied = self.client.get("/api/v1/auth/me/")
        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_revoke_another_users_session(self):
        other_user = get_user_model().objects.create_user(
            username="other.user",
            password="Another-Strong-Password-42!",
            organization=self.organization,
        )
        other_session = ApiSession.objects.create(
            user=other_user,
            token_digest="a" * 64,
            expires_at=timezone.now() + timedelta(hours=1),
            idle_expires_at=timezone.now() + timedelta(hours=1),
        )

        response = self.login()
        self.authorize(response.data["token"])

        denied = self.client.post(
            f"/api/v1/auth/sessions/{other_session.id}/revoke/"
        )

        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)
        other_session.refresh_from_db()
        self.assertIsNone(other_session.revoked_at)

    def test_invalid_login_does_not_disclose_account_existence(self):
        known = self.client.post(
            "/api/v1/auth/login/",
            {"login": "atelier.user", "password": "wrong-password"},
            format="json",
        )
        unknown = self.client.post(
            "/api/v1/auth/login/",
            {"login": "missing.user", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(known.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(unknown.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(known.data["error"]["code"], "authentication_required")
        self.assertEqual(unknown.data["error"]["code"], "authentication_required")
        self.assertEqual(known.data["error"]["message"], unknown.data["error"]["message"])
