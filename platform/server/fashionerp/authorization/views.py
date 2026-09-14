from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from fashionerp.audit.services import audit_snapshot, record_audit_event
from fashionerp.identity.exceptions import InvalidSecondFactor
from fashionerp.identity.models import ApiSession
from fashionerp.identity.serializers import ReauthenticationSerializer
from fashionerp.identity.services import (
    disable_two_factor,
    revoke_user_sessions,
    two_factor_enabled,
    verify_second_factor,
)

from .models import AccessGrant, AccessGroup, Permission, Role
from .permissions import CanManageAccess
from .serializers import (
    AccessGrantSerializer,
    AccessGroupSerializer,
    AccessUserSerializer,
    PermissionSerializer,
    RoleSerializer,
)


def _audit_mutation(*, request, action, instance, before=None, metadata=None):
    record_audit_event(
        organization=request.user.organization,
        actor=request.user,
        action=action,
        object_instance=instance,
        before=before,
        after=audit_snapshot(instance),
        request=request,
        metadata=metadata,
    )


class PermissionListView(generics.ListAPIView):
    serializer_class = PermissionSerializer
    permission_classes = [CanManageAccess]
    pagination_class = None
    queryset = Permission.objects.all()


class RoleListCreateView(generics.ListCreateAPIView):
    serializer_class = RoleSerializer
    permission_classes = [CanManageAccess]

    def get_queryset(self):
        return Role.objects.filter(
            organization_id=self.request.user.organization_id
        ).prefetch_related("permissions")

    def perform_create(self, serializer):
        with transaction.atomic():
            role = serializer.save()
            _audit_mutation(
                request=self.request,
                action="access.role.create",
                instance=role,
            )


class RoleDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = RoleSerializer
    permission_classes = [CanManageAccess]
    lookup_url_kwarg = "role_id"

    def get_queryset(self):
        return Role.objects.filter(
            organization_id=self.request.user.organization_id
        ).prefetch_related("permissions")

    def perform_update(self, serializer):
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            role = serializer.save()
            _audit_mutation(
                request=self.request,
                action="access.role.update",
                instance=role,
                before=before,
            )


class GroupListCreateView(generics.ListCreateAPIView):
    serializer_class = AccessGroupSerializer
    permission_classes = [CanManageAccess]

    def get_queryset(self):
        return AccessGroup.objects.filter(
            organization_id=self.request.user.organization_id
        ).prefetch_related("members")

    def perform_create(self, serializer):
        with transaction.atomic():
            group = serializer.save()
            _audit_mutation(
                request=self.request,
                action="access.group.create",
                instance=group,
            )


class GroupDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AccessGroupSerializer
    permission_classes = [CanManageAccess]
    lookup_url_kwarg = "group_id"

    def get_queryset(self):
        return AccessGroup.objects.filter(
            organization_id=self.request.user.organization_id
        ).prefetch_related("members")

    def perform_update(self, serializer):
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            group = serializer.save()
            _audit_mutation(
                request=self.request,
                action="access.group.update",
                instance=group,
                before=before,
            )


class GrantListCreateView(generics.ListCreateAPIView):
    serializer_class = AccessGrantSerializer
    permission_classes = [CanManageAccess]

    def get_queryset(self):
        return AccessGrant.objects.filter(
            role__organization_id=self.request.user.organization_id
        ).select_related(
            "role",
            "user",
            "group",
            "company",
            "establishment",
        )

    def perform_create(self, serializer):
        with transaction.atomic():
            grant = serializer.save()
            _audit_mutation(
                request=self.request,
                action="access.grant.create",
                instance=grant,
            )


class GrantRevokeView(APIView):
    permission_classes = [CanManageAccess]

    @extend_schema(request=None, responses={204: None})
    def post(self, request, grant_id):
        try:
            grant = AccessGrant.objects.select_related("role").get(
                pk=grant_id,
                role__organization_id=request.user.organization_id,
            )
        except AccessGrant.DoesNotExist as exc:
            raise NotFound("Access grant not found.") from exc

        if (
            grant.user_id == request.user.id
            and grant.role.is_system
            and grant.role.is_full_access
        ):
            active_admin_grants = AccessGrant.objects.filter(
                role=grant.role,
                revoked_at__isnull=True,
            ).count()
            if active_admin_grants <= 1:
                raise PermissionDenied(
                    "The last organization administrator grant cannot be revoked."
                )

        with transaction.atomic():
            before = audit_snapshot(grant)
            grant.revoke()
            _audit_mutation(
                request=request,
                action="access.grant.revoke",
                instance=grant,
                before=before,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccessUserListView(generics.ListCreateAPIView):
    serializer_class = AccessUserSerializer
    permission_classes = [CanManageAccess]

    def get_queryset(self):
        return get_user_model().objects.filter(
            organization_id=self.request.user.organization_id
        ).order_by("username")

    def perform_create(self, serializer):
        with transaction.atomic():
            user = serializer.save()
            _audit_mutation(
                request=self.request,
                action="access.user.create",
                instance=user,
            )


class AccessUserTwoFactorResetView(APIView):
    permission_classes = [CanManageAccess]

    @extend_schema(request=ReauthenticationSerializer, responses={204: None})
    def post(self, request, user_id):
        if user_id == request.user.id:
            raise PermissionDenied(
                "Use the personal 2FA disable flow for your own account."
            )

        try:
            target = get_user_model().objects.get(
                pk=user_id,
                organization_id=request.user.organization_id,
            )
        except get_user_model().DoesNotExist as exc:
            raise NotFound("User not found.") from exc

        serializer = ReauthenticationSerializer(
            data=request.data,
            context={"request": request, "allow_recovery": True},
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            method = serializer.validated_data.get("second_factor_method")
            if method == "recovery":
                consumed = verify_second_factor(
                    request.user,
                    serializer.validated_data.get("two_factor_code", ""),
                    consume_recovery=True,
                )
                if consumed != "recovery":
                    raise InvalidSecondFactor()

            was_enabled = two_factor_enabled(target)
            disable_two_factor(target)
            revoked = revoke_user_sessions(
                target,
                reason="administrator_two_factor_reset",
            )
            record_audit_event(
                organization=request.user.organization,
                actor=request.user,
                action="access.user.2fa_reset",
                object_type="identity.user",
                object_id=str(target.id),
                object_label=target.username,
                request=request,
                metadata={
                    "two_factor_was_enabled": was_enabled,
                    "sessions_revoked": revoked,
                },
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccessUserDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AccessUserSerializer
    permission_classes = [CanManageAccess]
    lookup_url_kwarg = "user_id"

    def get_queryset(self):
        return get_user_model().objects.filter(
            organization_id=self.request.user.organization_id
        )

    def perform_update(self, serializer):
        with transaction.atomic():
            before = audit_snapshot(serializer.instance)
            active_sessions_before = serializer.instance.api_sessions.filter(
                revoked_at__isnull=True
            ).count()
            user = serializer.save()
            active_sessions_after = user.api_sessions.filter(
                revoked_at__isnull=True
            ).count()
            _audit_mutation(
                request=self.request,
                action="access.user.update",
                instance=user,
                before=before,
                metadata={
                    "sessions_revoked": max(
                        active_sessions_before - active_sessions_after,
                        0,
                    ),
                    "password_changed": "password" in serializer.validated_data,
                },
            )
