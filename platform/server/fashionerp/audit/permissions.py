from rest_framework.permissions import BasePermission

from fashionerp.authorization.services import has_permission


class CanViewAudit(BasePermission):
    message = "You do not have permission to view the audit journal."

    def has_permission(self, request, view) -> bool:
        return has_permission(
            request.user,
            "foundation.audit.view",
        )
