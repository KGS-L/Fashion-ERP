from django.contrib.auth import get_user_model
from rest_framework import serializers

from fashionerp.organizations.models import Company, Establishment

from .models import AccessGrant, AccessGroup, Permission, Role


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("id", "code", "module", "action", "name", "description")
        read_only_fields = fields


class RoleSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SlugRelatedField(
        source="permissions",
        slug_field="code",
        queryset=Permission.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = Role
        fields = (
            "id",
            "code",
            "name",
            "description",
            "permission_codes",
            "is_full_access",
            "is_system",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "is_full_access",
            "is_system",
            "created_at",
            "updated_at",
        )

    def create(self, validated_data):
        permissions = validated_data.pop("permissions", [])
        role = Role.objects.create(
            organization=self.context["request"].user.organization,
            **validated_data,
        )
        role.permissions.set(permissions)
        return role

    def update(self, instance, validated_data):
        if instance.is_system:
            raise serializers.ValidationError(
                "System roles cannot be modified through the API."
            )
        permissions = validated_data.pop("permissions", None)
        instance = super().update(instance, validated_data)
        if permissions is not None:
            instance.permissions.set(permissions)
        return instance


class AccessGroupSerializer(serializers.ModelSerializer):
    member_ids = serializers.PrimaryKeyRelatedField(
        source="members",
        queryset=get_user_model().objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = AccessGroup
        fields = (
            "id",
            "code",
            "name",
            "description",
            "member_ids",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_member_ids(self, members):
        organization_id = self.context["request"].user.organization_id
        if any(member.organization_id != organization_id for member in members):
            raise serializers.ValidationError(
                "All group members must belong to the local organization."
            )
        return members

    def create(self, validated_data):
        members = validated_data.pop("members", [])
        group = AccessGroup.objects.create(
            organization=self.context["request"].user.organization,
            **validated_data,
        )
        group.members.set(members)
        return group

    def update(self, instance, validated_data):
        members = validated_data.pop("members", None)
        instance = super().update(instance, validated_data)
        if members is not None:
            instance.members.set(members)
        return instance


class AccessGrantSerializer(serializers.ModelSerializer):
    role_id = serializers.PrimaryKeyRelatedField(
        source="role",
        queryset=Role.objects.all(),
    )
    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=get_user_model().objects.all(),
        allow_null=True,
        required=False,
    )
    group_id = serializers.PrimaryKeyRelatedField(
        source="group",
        queryset=AccessGroup.objects.all(),
        allow_null=True,
        required=False,
    )
    company_id = serializers.PrimaryKeyRelatedField(
        source="company",
        queryset=Company.objects.all(),
        allow_null=True,
        required=False,
    )
    establishment_id = serializers.PrimaryKeyRelatedField(
        source="establishment",
        queryset=Establishment.objects.all(),
        allow_null=True,
        required=False,
    )
    scope_type = serializers.CharField(read_only=True)

    class Meta:
        model = AccessGrant
        fields = (
            "id",
            "role_id",
            "user_id",
            "group_id",
            "company_id",
            "establishment_id",
            "scope_type",
            "created_at",
            "revoked_at",
        )
        read_only_fields = ("id", "scope_type", "created_at", "revoked_at")

    def validate(self, attrs):
        organization_id = self.context["request"].user.organization_id
        user = attrs.get("user")
        group = attrs.get("group")
        role = attrs.get("role")
        company = attrs.get("company")
        establishment = attrs.get("establishment")

        if bool(user) == bool(group):
            raise serializers.ValidationError(
                "Exactly one principal, user or group, is required."
            )
        if role.organization_id != organization_id:
            raise serializers.ValidationError("Role is outside the local organization.")
        if user and user.organization_id != organization_id:
            raise serializers.ValidationError("User is outside the local organization.")
        if group and group.organization_id != organization_id:
            raise serializers.ValidationError("Group is outside the local organization.")
        if company and company.organization_id != organization_id:
            raise serializers.ValidationError("Company is outside the local organization.")
        if (
            establishment
            and establishment.company.organization_id != organization_id
        ):
            raise serializers.ValidationError(
                "Establishment is outside the local organization."
            )
        if company and establishment:
            raise serializers.ValidationError(
                "Choose either company or establishment scope, not both."
            )
        return attrs

    def create(self, validated_data):
        grant = AccessGrant(**validated_data)
        grant.full_clean()
        grant.save()
        return grant


class AccessUserSerializer(serializers.ModelSerializer):
    login = serializers.CharField(source="username", read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "login",
            "first_name",
            "last_name",
            "email",
            "is_active",
        )
        read_only_fields = fields
