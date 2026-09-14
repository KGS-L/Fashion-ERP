from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AccessGrant, AccessGroup, Permission, Role
from .permissions import CanManageAccess
from .serializers import (
    AccessGrantSerializer,
    AccessGroupSerializer,
    AccessUserSerializer,
    PermissionSerializer,
    RoleSerializer,
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


class RoleDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = RoleSerializer
    permission_classes = [CanManageAccess]
    lookup_url_kwarg = "role_id"

    def get_queryset(self):
        return Role.objects.filter(
            organization_id=self.request.user.organization_id
        ).prefetch_related("permissions")


class GroupListCreateView(generics.ListCreateAPIView):
    serializer_class = AccessGroupSerializer
    permission_classes = [CanManageAccess]

    def get_queryset(self):
        return AccessGroup.objects.filter(
            organization_id=self.request.user.organization_id
        ).prefetch_related("members")


class GroupDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AccessGroupSerializer
    permission_classes = [CanManageAccess]
    lookup_url_kwarg = "group_id"

    def get_queryset(self):
        return AccessGroup.objects.filter(
            organization_id=self.request.user.organization_id
        ).prefetch_related("members")


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

        grant.revoke()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccessUserListView(generics.ListAPIView):
    serializer_class = AccessUserSerializer
    permission_classes = [CanManageAccess]

    def get_queryset(self):
        return get_user_model().objects.filter(
            organization_id=self.request.user.organization_id
        ).order_by("username")
