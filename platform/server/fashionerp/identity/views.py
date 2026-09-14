from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from fashionerp.audit.services import audit_snapshot, record_audit_event

from .models import ApiSession
from .serializers import (
    ApiSessionSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    UserSerializer,
)
from .services import create_api_session


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: LoginResponseSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        with transaction.atomic():
            session, raw_token = create_api_session(
                user=user,
                device_id=serializer.validated_data.get("device_id", ""),
                device_label=serializer.validated_data.get("device_label", ""),
                user_agent=request.headers.get("User-Agent", ""),
            )
            record_audit_event(
                organization=user.organization,
                actor=user,
                action="auth.login",
                object_instance=session,
                after=audit_snapshot(session),
                request=request,
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
