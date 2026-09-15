import pyotp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from ivadoo.audit.models import AuditEvent
from ivadoo.authorization.services import grant_organization_admin
from ivadoo.organizations.models import Organization

from .models import ApiSession, RecoveryCode, TotpCredential


class TwoFactorAuthenticationTests(APITestCase):
    password = "Strong-Test-Password-42!"

    def setUp(self):
        cache.clear()
        self.organization = Organization.objects.create(
            name="2FA Test Organization",
            slug="two-factor-test",
        )
        self.user = get_user_model().objects.create_user(
            username="secure.user",
            password=self.password,
            email="secure@example.test",
            organization=self.organization,
        )

    def login(self, *, code=None, device_id="device-a"):
        payload = {
            "login": self.user.username,
            "password": self.password,
            "device_id": device_id,
            "device_label": device_id,
        }
        if code is not None:
            payload["two_factor_code"] = code
        return self.client.post(
            "/api/v1/auth/login/",
            payload,
            format="json",
        )

    def authorize(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def setup_two_factor(self):
        login = self.login()
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.authorize(login.data["token"])

        setup = self.client.post(
            "/api/v1/auth/2fa/totp/setup/",
            {"password": self.password},
            format="json",
        )
        self.assertEqual(setup.status_code, status.HTTP_200_OK)
        secret = setup.data["secret"]
        code = pyotp.TOTP(secret).now()

        confirm = self.client.post(
            "/api/v1/auth/2fa/totp/confirm/",
            {"code": code},
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        return secret, confirm.data["recovery_codes"], login.data["token"]

    def test_setup_encrypts_secret_and_confirmation_returns_recovery_codes_once(self):
        login = self.login()
        self.authorize(login.data["token"])

        setup = self.client.post(
            "/api/v1/auth/2fa/totp/setup/",
            {"password": self.password},
            format="json",
        )

        self.assertEqual(setup.status_code, status.HTTP_200_OK)
        secret = setup.data["secret"]
        credential = TotpCredential.objects.get(user=self.user)
        self.assertNotEqual(credential.encrypted_secret, secret)
        self.assertNotIn(secret, credential.encrypted_secret)

        confirm = self.client.post(
            "/api/v1/auth/2fa/totp/confirm/",
            {"code": pyotp.TOTP(secret).now()},
            format="json",
        )

        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        codes = confirm.data["recovery_codes"]
        self.assertEqual(len(codes), 10)
        self.assertEqual(
            RecoveryCode.objects.filter(user=self.user).count(),
            10,
        )
        stored = set(
            RecoveryCode.objects.filter(user=self.user).values_list(
                "code_digest",
                flat=True,
            )
        )
        self.assertTrue(all(code not in stored for code in codes))

        events = AuditEvent.objects.filter(
            action__in=("auth.2fa.setup_started", "auth.2fa.enabled")
        )
        serialized = " ".join(str(event.metadata) for event in events)
        self.assertNotIn(secret, serialized)
        self.assertTrue(all(code not in serialized for code in codes))

    def test_enabled_two_factor_blocks_password_only_login(self):
        secret, _, _ = self.setup_two_factor()
        self.client.credentials()

        missing = self.login()
        invalid = self.login(code="000000")
        valid = self.login(code=pyotp.TOTP(secret).now())

        self.assertEqual(missing.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            missing.data["error"]["code"],
            "two_factor_required",
        )
        self.assertEqual(invalid.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            invalid.data["error"]["code"],
            "invalid_two_factor",
        )
        self.assertEqual(valid.status_code, status.HTTP_200_OK)
        session = ApiSession.objects.get(pk=valid.data["session"]["id"])
        self.assertTrue(session.two_factor_verified)

    def test_recovery_code_can_login_only_once(self):
        _, recovery_codes, _ = self.setup_two_factor()
        recovery = recovery_codes[0]
        self.client.credentials()

        first = self.login(code=recovery, device_id="recovery-device")
        second = self.login(code=recovery, device_id="reused-device")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            second.data["error"]["code"],
            "invalid_two_factor",
        )

    def test_enabling_two_factor_revokes_other_existing_sessions(self):
        first = self.login(device_id="first")
        second = self.login(device_id="second")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)

        self.authorize(first.data["token"])
        setup = self.client.post(
            "/api/v1/auth/2fa/totp/setup/",
            {"password": self.password},
            format="json",
        )
        secret = setup.data["secret"]
        confirm = self.client.post(
            "/api/v1/auth/2fa/totp/confirm/",
            {"code": pyotp.TOTP(secret).now()},
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)

        first_session = ApiSession.objects.get(pk=first.data["session"]["id"])
        second_session = ApiSession.objects.get(pk=second.data["session"]["id"])
        self.assertIsNone(first_session.revoked_at)
        self.assertTrue(first_session.two_factor_verified)
        self.assertIsNotNone(second_session.revoked_at)
        self.assertEqual(
            second_session.revocation_reason,
            "two_factor_enabled",
        )

    def test_user_can_revoke_all_other_sessions(self):
        first = self.login(device_id="first")
        second = self.login(device_id="second")
        self.authorize(first.data["token"])

        response = self.client.post(
            "/api/v1/auth/sessions/revoke-others/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["revoked_sessions"], 1)
        self.assertIsNone(
            ApiSession.objects.get(pk=first.data["session"]["id"]).revoked_at
        )
        self.assertIsNotNone(
            ApiSession.objects.get(pk=second.data["session"]["id"]).revoked_at
        )

    def test_disable_requires_reauthentication_and_revokes_other_sessions(self):
        secret, _, current_token = self.setup_two_factor()
        self.client.credentials()
        other = self.login(
            code=pyotp.TOTP(secret).now(),
            device_id="other",
        )
        self.assertEqual(other.status_code, status.HTTP_200_OK)

        self.authorize(current_token)
        response = self.client.post(
            "/api/v1/auth/2fa/disable/",
            {
                "password": self.password,
                "two_factor_code": pyotp.TOTP(secret).now(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TotpCredential.objects.filter(user=self.user).exists())
        self.assertFalse(RecoveryCode.objects.filter(user=self.user).exists())
        self.assertIsNotNone(
            ApiSession.objects.get(pk=other.data["session"]["id"]).revoked_at
        )

    def test_recovery_code_regeneration_requires_totp_not_recovery_code(self):
        secret, recovery_codes, current_token = self.setup_two_factor()
        self.authorize(current_token)

        denied = self.client.post(
            "/api/v1/auth/2fa/recovery-codes/regenerate/",
            {
                "password": self.password,
                "two_factor_code": recovery_codes[0],
            },
            format="json",
        )
        allowed = self.client.post(
            "/api/v1/auth/2fa/recovery-codes/regenerate/",
            {
                "password": self.password,
                "two_factor_code": pyotp.TOTP(secret).now(),
            },
            format="json",
        )

        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(allowed.data["recovery_codes"]), 10)


class AdministratorTwoFactorResetTests(APITestCase):
    admin_password = "Admin-Strong-Password-42!"
    target_password = "Target-Strong-Password-42!"

    def setUp(self):
        cache.clear()
        self.organization = Organization.objects.create(
            name="Admin 2FA Organization",
            slug="admin-two-factor-test",
        )
        self.admin = get_user_model().objects.create_user(
            username="security.admin",
            password=self.admin_password,
            organization=self.organization,
        )
        grant_organization_admin(user=self.admin)
        self.target = get_user_model().objects.create_user(
            username="target.user",
            password=self.target_password,
            organization=self.organization,
        )

        admin_login = self.client.post(
            "/api/v1/auth/login/",
            {
                "login": self.admin.username,
                "password": self.admin_password,
            },
            format="json",
        )
        self.assertEqual(admin_login.status_code, status.HTTP_200_OK)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {admin_login.data['token']}"
        )

    def _enable_target_2fa_and_session(self):
        target_client = self.client_class()
        login = target_client.post(
            "/api/v1/auth/login/",
            {
                "login": self.target.username,
                "password": self.target_password,
            },
            format="json",
        )
        target_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['token']}"
        )
        setup = target_client.post(
            "/api/v1/auth/2fa/totp/setup/",
            {"password": self.target_password},
            format="json",
        )
        confirm = target_client.post(
            "/api/v1/auth/2fa/totp/confirm/",
            {"code": pyotp.TOTP(setup.data["secret"]).now()},
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        return ApiSession.objects.get(pk=login.data["session"]["id"])

    def test_admin_reset_removes_2fa_revokes_sessions_and_is_audited(self):
        target_session = self._enable_target_2fa_and_session()

        response = self.client.post(
            f"/api/v1/access/users/{self.target.id}/2fa/reset/",
            {"password": self.admin_password},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            TotpCredential.objects.filter(user=self.target).exists()
        )
        target_session.refresh_from_db()
        self.assertIsNotNone(target_session.revoked_at)
        self.assertEqual(
            target_session.revocation_reason,
            "administrator_two_factor_reset",
        )
        event = AuditEvent.objects.get(action="access.user.2fa_reset")
        self.assertEqual(event.actor_id, self.admin.id)
        self.assertEqual(event.object_id, str(self.target.id))

    def test_admin_cannot_use_reset_route_to_bypass_own_2fa_controls(self):
        response = self.client.post(
            f"/api/v1/access/users/{self.admin.id}/2fa/reset/",
            {"password": self.admin_password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
