from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from .exceptions import InvalidSecondFactor, TwoFactorRequired
from .models import ApiSession, User
from .services import (
    remaining_recovery_codes,
    two_factor_enabled,
    verify_second_factor,
)


class LoginSerializer(serializers.Serializer):
    login = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    two_factor_code = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        max_length=32,
    )
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

        second_factor_method = None
        if two_factor_enabled(user):
            code = attrs.get("two_factor_code")
            if not code:
                raise TwoFactorRequired()
            second_factor_method = verify_second_factor(
                user,
                code,
                consume_recovery=False,
            )
            if second_factor_method is None:
                raise InvalidSecondFactor()

        attrs["user"] = user
        attrs["second_factor_method"] = second_factor_method
        return attrs


class ReauthenticationSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    two_factor_code = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        max_length=32,
    )

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user

        if not user.check_password(attrs["password"]):
            raise AuthenticationFailed("Invalid authentication credentials.")

        second_factor_method = None
        if two_factor_enabled(user):
            code = attrs.get("two_factor_code")
            if not code:
                raise TwoFactorRequired()

            allow_recovery = self.context.get("allow_recovery", True)
            second_factor_method = verify_second_factor(
                user,
                code,
                allow_recovery=allow_recovery,
                consume_recovery=False,
            )
            if second_factor_method is None:
                raise InvalidSecondFactor()

        attrs["second_factor_method"] = second_factor_method
        return attrs


class TotpConfirmSerializer(serializers.Serializer):
    code = serializers.CharField(
        write_only=True,
        min_length=6,
        max_length=6,
    )


class UserSerializer(serializers.ModelSerializer):
    login = serializers.CharField(source="username", read_only=True)
    two_factor_enabled = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "login",
            "first_name",
            "last_name",
            "email",
            "language_code",
            "is_active",
            "two_factor_enabled",
        )
        read_only_fields = fields

    def get_two_factor_enabled(self, obj) -> bool:
        return two_factor_enabled(obj)


class ApiSessionSerializer(serializers.ModelSerializer):
    current = serializers.SerializerMethodField()

    class Meta:
        model = ApiSession
        fields = (
            "id",
            "device_id",
            "device_label",
            "user_agent",
            "ip_address",
            "two_factor_verified",
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


class TwoFactorStatusSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(read_only=True)
    confirmed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    recovery_codes_remaining = serializers.IntegerField(read_only=True)


class TotpSetupResponseSerializer(serializers.Serializer):
    secret = serializers.CharField(read_only=True)
    provisioning_uri = serializers.CharField(read_only=True)


class RecoveryCodesResponseSerializer(serializers.Serializer):
    recovery_codes = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
    )


class SessionRevocationResponseSerializer(serializers.Serializer):
    revoked_sessions = serializers.IntegerField(read_only=True)
