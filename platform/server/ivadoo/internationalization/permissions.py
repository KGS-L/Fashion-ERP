from rest_framework.permissions import BasePermission, SAFE_METHODS

from ivadoo.authorization.services import has_permission


class CanAccessInternationalSettings(BasePermission):
    message = "You do not have permission to access international settings."

    def has_permission(self, request, view) -> bool:
        permission_code = (
            "foundation.i18n.view"
            if request.method in SAFE_METHODS
            else "foundation.i18n.manage"
        )
        return has_permission(request.user, permission_code)
