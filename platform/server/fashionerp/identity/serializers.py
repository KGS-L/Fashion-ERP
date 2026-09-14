from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiSession, User


class LoginSerializer(serializers.Serializer):
    login = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    device_id = serializers.CharField(max_length=128, required=False, allow_blank=True)
    device_label = serializers.CharField(max_length=128, required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context.get("request")
        user = authenticate(
            request=request,
            username=attrs["login"],
            password=attrs["password"],
        )

        if user is None:
            raise AuthenticationFailed("Invalid login or password.")

        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    login = serializers.CharField(source="username", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "login",
            "first_name",
            "last_name",
            "email",
            "is_active",
        )
        read_only_fields = fields


class ApiSessionSerializer(serializers.ModelSerializer):
    current = serializers.SerializerMethodField()

    class Meta:
        model = ApiSession
        fields = (
            "id",
            "device_id",
            "device_label",
            "user_agent",
            "created_at",
            "last_seen_at",
            "expires_at",
            "idle_expires_at",
            "revoked_at",
            "current",
        )
        read_only_fields = fields

    def get_current(self, obj) -> bool:
        request = self.context.get("request")
        current_session = getattr(request, "auth", None) if request is not None else None
        return bool(current_session and current_session.pk == obj.pk)


class LoginResponseSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    token_type = serializers.CharField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)
    session = ApiSessionSerializer(read_only=True)
    user = UserSerializer(read_only=True)
