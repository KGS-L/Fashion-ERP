from django.db import transaction
from django.utils import timezone, translation
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import AuthenticationFailed, NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from fashionerp.audit.models import AuditEvent
from fashionerp.audit.services import audit_snapshot, record_audit_event
from fashionerp.organizations.models import Organization

from .exceptions import InvalidSecondFactor
from .models import ApiSession, TotpCredential
from .serializers import (
    ApiSessionSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    ReauthenticationSerializer,
    RecoveryCodesResponseSerializer,
    SessionRevocationResponseSerializer,
    TotpConfirmSerializer,
    TotpSetupResponseSerializer,
    TwoFactorStatusSerializer,
    UserSerializer,
)
from .services import (
    begin_totp_setup,
    confirm_totp_setup,
    create_api_session,
    disable_two_factor,
    remaining_recovery_codes,
    replace_recovery_codes,
    revoke_user_sessions,
    two_factor_enabled,
    verify_second_factor,
)


def _request_ip(request):
    return request.META.get("REMOTE_ADDR") or None


def _consume_recovery_if_needed(user, code, method):
    if method != "recovery":
        return
    consumed = verify_second_factor(
        user,
        code,
        allow_recovery=True,
        consume_recovery=True,
    )
    if consumed != "recovery":
        raise InvalidSecondFactor()


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_authenticate_header(self, request) -> str:
        return "Bearer"

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: LoginResponseSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed:
            organization = Organization.objects.first()
            if organization is not None:
                record_audit_event(
                    organization=organization,
                    action="auth.login",
                    object_type="identity.login",
                    object_label=str(request.data.get("login", ""))[:255],
                    result=AuditEvent.Result.FAILURE,
                    request=request,
                    metadata={"reason": "authentication_failed"},
                )
            raise

        user = serializer.validated_data["user"]
        second_factor_method = serializer.validated_data["second_factor_method"]
        translation.activate(user.language_code)

        with transaction.atomic():
            _consume_recovery_if_needed(
                user,
                serializer.validated_data.get("two_factor_code", ""),
                second_factor_method,
            )
            session, raw_token = create_api_session(
                user=user,
                device_id=serializer.validated_data.get("device_id", ""),
                device_label=serializer.validated_data.get("device_label", ""),
                user_agent=request.headers.get("User-Agent", ""),
                ip_address=_request_ip(request),
                two_factor_verified=second_factor_method is not None,
            )
            record_audit_event(
                organization=user.organization,
                actor=user,
                action="auth.login",
                object_instance=session,
                after=audit_snapshot(session),
                request=request,
                metadata={
                    "second_factor": second_factor_method or "not_enabled",
                },
            )

        return Response(
            {
                "token": raw_token,
                "token_type": "Bearer",
                "expires_at": session.expires_at,
                "session": ApiSessionSerializer(
                    session,
                    context={"request": request},
                ).data,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        session = request.auth
        if isinstance(session, ApiSession):
            with transaction.atomic():
                before = audit_snapshot(session)
                session.revoke(reason="logout")
                record_audit_event(
                    organization=request.user.organization,
                    actor=request.user,
                    action="auth.logout",
                    object_instance=session,
                    before=before,
                    after=audit_snapshot(session),
                    request=request,
                )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class SessionListView(generics.ListAPIView):
    serializer_class = ApiSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        now = timezone.now()
        return ApiSession.objects.filter(
            user=self.request.user,
            revoked_at__isnull=True,
            expires_at__gt=now,
            idle_expires_at__gt=now,
        ).order_by("-created_at")


class SessionRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request, session_id):
        try:
            session = ApiSession.objects.get(
                pk=session_id,
                user=request.user,
            )
        except ApiSession.DoesNotExist as exc:
            raise NotFound("Session not found.") from exc

        with transaction.atomic():
            before = audit_snapshot(session)
            session.revoke(reason="user_requested")
            record_audit_event(
                organization=request.user.organization,
                actor=request.user,
                action="auth.session.revoke",
                object_instance=session,
                before=before,
                after=audit_snapshot(session),
                request=request,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionRevokeOthersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: SessionRevocationResponseSerializer},
    )
    def post(self, request):
        current = request.auth if isinstance(request.auth, ApiSession) else None
        with transaction.atomic():
            revoked = revoke_user_sessions(
                request.user,
                reason="user_revoke_others",
                exclude_session_id=current.id if current else None,
            )
            record_audit_event(
                organization=request.user.organization,
                actor=request.user,
                action="auth.sessions.revoke_others",
                object_type="identity.user",
                object_id=str(request.user.id),
                object_label=request.user.username,
                request=request,
                metadata={"revoked_sessions": revoked},
            )
        return Response({"revoked_sessions": revoked})


class TwoFactorStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: TwoFactorStatusSerializer})
    def get(self, request):
        try:
            credential = request.user.totp_credential
        except TotpCredential.DoesNotExist:
            credential = None
        enabled = bool(credential and credential.is_confirmed)
        return Response(
            {
                "enabled": enabled,
                "confirmed_at": (
                    credential.confirmed_at if enabled else None
                ),
                "recovery_codes_remaining": (
                    remaining_recovery_codes(request.user) if enabled else 0
                ),
            }
        )


class TotpSetupView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReauthenticationSerializer,
        responses={200: TotpSetupResponseSerializer},
    )
    def post(self, request):
        serializer = ReauthenticationSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        if two_factor_enabled(request.user):
            raise ValidationError("Two-factor authentication is already enabled.")

        with transaction.atomic():
            _, secret, uri = begin_totp_setup(request.user)
            record_audit_event(
                organization=request.user.organization,
                actor=request.user,
                action="auth.2fa.setup_started",
                object_type="identity.user",
                object_id=str(request.user.id),
                object_label=request.user.username,
                request=request,
            )
        return Response({"secret": secret, "provisioning_uri": uri})


class TotpConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=TotpConfirmSerializer,
        responses={200: RecoveryCodesResponseSerializer},
    )
    def post(self, request):
        serializer = TotpConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            try:
                recovery_codes = confirm_totp_setup(
                    request.user,
                    serializer.validated_data["code"],
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

            current = request.auth if isinstance(request.auth, ApiSession) else None
            if current:
                current.two_factor_verified = True
                current.save(update_fields=["two_factor_verified"])

            revoked = revoke_user_sessions(
                request.user,
                reason="two_factor_enabled",
                exclude_session_id=current.id if current else None,
            )
            record_audit_event(
                organization=request.user.organization,
                actor=request.user,
                action="auth.2fa.enabled",
                object_type="identity.user",
                object_id=str(request.user.id),
                object_label=request.user.username,
                request=request,
                metadata={
                    "recovery_codes_generated": len(recovery_codes),
                    "sessions_revoked": revoked,
                },
            )
        return Response({"recovery_codes": recovery_codes})


class TwoFactorDisableView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ReauthenticationSerializer, responses={204: None})
    def post(self, request):
        if not two_factor_enabled(request.user):
            raise ValidationError("Two-factor authentication is not enabled.")

        serializer = ReauthenticationSerializer(
            data=request.data,
            context={"request": request, "allow_recovery": True},
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            _consume_recovery_if_needed(
                request.user,
                serializer.validated_data.get("two_factor_code", ""),
                serializer.validated_data.get("second_factor_method"),
            )
            disable_two_factor(request.user)
            current = request.auth if isinstance(request.auth, ApiSession) else None
            if current:
                current.two_factor_verified = False
                current.save(update_fields=["two_factor_verified"])
            revoked = revoke_user_sessions(
                request.user,
                reason="two_factor_disabled",
                exclude_session_id=current.id if current else None,
            )
            record_audit_event(
                organization=request.user.organization,
                actor=request.user,
                action="auth.2fa.disabled",
                object_type="identity.user",
                object_id=str(request.user.id),
                object_label=request.user.username,
                request=request,
                metadata={"sessions_revoked": revoked},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecoveryCodesRegenerateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReauthenticationSerializer,
        responses={200: RecoveryCodesResponseSerializer},
    )
    def post(self, request):
        if not two_factor_enabled(request.user):
            raise ValidationError("Two-factor authentication is not enabled.")

        serializer = ReauthenticationSerializer(
            data=request.data,
            context={"request": request, "allow_recovery": False},
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            recovery_codes = replace_recovery_codes(request.user)
            record_audit_event(
                organization=request.user.organization,
                actor=request.user,
                action="auth.2fa.recovery_codes_regenerated",
                object_type="identity.user",
                object_id=str(request.user.id),
                object_label=request.user.username,
                request=request,
                metadata={"recovery_codes_generated": len(recovery_codes)},
            )
        return Response({"recovery_codes": recovery_codes})
