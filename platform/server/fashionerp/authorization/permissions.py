from rest_framework.permissions import BasePermission

from .services import has_permission


class CanManageAccess(BasePermission):
    message = "You do not have permission to manage access."

    def has_permission(self, request, view) -> bool:
        return has_permission(
            request.user,
            "foundation.access.manage",
        )
