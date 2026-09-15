from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from fashionerp.audit.services import record_audit_event
from fashionerp.authorization.services import has_permission

from .metadata import can_view_model, metadata_etag, model_metadata, visible_model_metadata
from .models import CustomFieldDefinition
from .registry import get_model_manifest
from .serializers import CustomFieldDefinitionSerializer
from .services import list_module_states, module_state, set_module_state


def _require(user, permission_code: str, message: str) -> None:
    if not has_permission(user, permission_code):
        raise PermissionDenied(message)


def _metadata_response(request, payload):
    etag = metadata_etag(payload)
    if request.headers.get("If-None-Match") == etag:
        response = Response(status=status.HTTP_304_NOT_MODIFIED)
    else:
        response = Response(payload)
    response["ETag"] = etag
    response["Cache-Control"] = "private, must-revalidate"
    return response


class ModuleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require(request.user, "platform.module.view", "You do not have permission to view platform modules.")
        return Response(list_module_states(request.user.organization))


class ModuleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, module_code):
        _require(request.user, "platform.module.view", "You do not have permission to view platform modules.")
        try:
            payload = module_state(request.user.organization, module_code)
        except LookupError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(payload)


class ModuleActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, module_code, action):
        _require(request.user, "platform.module.manage", "You do not have permission to manage platform modules.")
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


class CustomFieldListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomFieldDefinitionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        _require(
            self.request.user,
            "platform.customization.view",
            "You do not have permission to view customization metadata.",
        )
        queryset = CustomFieldDefinition.objects.filter(
            organization=self.request.user.organization
        )
        model_key = self.request.query_params.get("model_key")
        if model_key:
            queryset = queryset.filter(model_key=model_key)
        return queryset

    def perform_create(self, serializer):
        _require(
            self.request.user,
            "platform.customization.manage",
            "You do not have permission to manage custom fields.",
        )
        with transaction.atomic():
            definition = serializer.save(
                organization=self.request.user.organization,
                created_by=self.request.user,
            )
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="platform.custom_field.create",
                object_instance=definition,
                after={
                    "model_key": definition.model_key,
                    "key": definition.key,
                    "field_type": definition.field_type,
                    "required": definition.required,
                    "is_active": definition.is_active,
                    "version": definition.version,
                },
                request=self.request,
            )


class CustomFieldDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = CustomFieldDefinitionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"
    lookup_url_kwarg = "field_id"

    def get_queryset(self):
        permission = (
            "platform.customization.view"
            if self.request.method == "GET"
            else "platform.customization.manage"
        )
        _require(
            self.request.user,
            permission,
            "You do not have permission to access custom fields.",
        )
        return CustomFieldDefinition.objects.filter(
            organization=self.request.user.organization
        )

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.instance
            before = {
                "label": instance.label,
                "field_type": instance.field_type,
                "required": instance.required,
                "options": instance.options,
                "validation": instance.validation,
                "is_active": instance.is_active,
                "version": instance.version,
            }
            definition = serializer.save(version=instance.version + 1)
            record_audit_event(
                organization=self.request.user.organization,
                actor=self.request.user,
                action="platform.custom_field.update",
                object_instance=definition,
                before=before,
                after={
                    "label": definition.label,
                    "field_type": definition.field_type,
                    "required": definition.required,
                    "options": definition.options,
                    "validation": definition.validation,
                    "is_active": definition.is_active,
                    "version": definition.version,
                },
                request=self.request,
            )


class MetadataModelListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = {"models": visible_model_metadata(request.user)}
        return _metadata_response(request, payload)


class MetadataModelDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, model_key):
        try:
            manifest = get_model_manifest(model_key)
        except LookupError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not can_view_model(request.user, manifest):
            return Response(status=status.HTTP_404_NOT_FOUND)
        return _metadata_response(request, model_metadata(request.user, manifest))
