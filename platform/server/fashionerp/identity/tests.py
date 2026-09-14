from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import ApiSession


class AuthenticationLifecycleTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="atelier.user",
            password="Strong-Test-Password-42!",
            email="atelier@example.test",
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
        self.assertEqual(len(sessions.data), 1)

        revoked = self.client.post(
            f"/api/v1/auth/sessions/{session_id}/revoke/"
        )
        self.assertEqual(revoked.status_code, status.HTTP_204_NO_CONTENT)

        denied = self.client.get("/api/v1/auth/me/")
        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)

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

        self.assertEqual(known.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(known.data["error"]["code"], "validation_error")
        self.assertEqual(unknown.data["error"]["code"], "validation_error")
