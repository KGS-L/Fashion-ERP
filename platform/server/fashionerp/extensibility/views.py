from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from fashionerp.authorization.services import has_permission

from .services import list_module_states, module_state, set_module_state


def _require(user, permission_code: str) -> None:
    if not has_permission(user, permission_code):
        raise PermissionDenied("You do not have permission to manage platform modules.")


class ModuleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require(request.user, "platform.module.view")
        return Response(list_module_states(request.user.organization))


class ModuleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, module_code):
        _require(request.user, "platform.module.view")
        try:
            payload = module_state(request.user.organization, module_code)
        except LookupError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(payload)


class ModuleActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, module_code, action):
        _require(request.user, "platform.module.manage")
        if action not in {"enable", "disable"}:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            set_module_state(
                organization=request.user.organization,
                module_code=module_code,
                enabled=action == "enable",
                actor=request.user,
                request=request,
            )
            payload = module_state(request.user.organization, module_code)
        except LookupError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            raise ValidationError(detail) from exc
        return Response(payload)
