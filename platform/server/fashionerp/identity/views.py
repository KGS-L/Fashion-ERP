from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import ApiSession
from .serializers import ApiSessionSerializer, LoginSerializer, UserSerializer
from .services import create_api_session


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        session, raw_token = create_api_session(
            user=user,
            device_id=serializer.validated_data.get("device_id", ""),
            device_label=serializer.validated_data.get("device_label", ""),
            user_agent=request.headers.get("User-Agent", ""),
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
            session.revoke(reason="logout")
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class SessionListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ApiSessionSerializer(many=True)})
    def get(self, request):
        now = timezone.now()
        sessions = (
            ApiSession.objects.filter(
                user=request.user,
                revoked_at__isnull=True,
                expires_at__gt=now,
                idle_expires_at__gt=now,
            )
            .order_by("-created_at")
        )
        return Response(
            ApiSessionSerializer(
                sessions,
                many=True,
                context={"request": request},
            ).data
        )


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

        session.revoke(reason="user_requested")
        return Response(status=status.HTTP_204_NO_CONTENT)
