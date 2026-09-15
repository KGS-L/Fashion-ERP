from django.core.exceptions import ValidationError

from ivadoo.authorization.models import Permission
from ivadoo.authorization.services import has_any_scope_permission, has_permission

from .registry import get_model_manifest


def object_scope(instance):
    company = getattr(instance, "company", None)
    establishment = getattr(instance, "establishment", None)
    if company is None and establishment is not None:
        company = establishment.company
    return company, establishment


def can_view_object(user, manifest, instance) -> bool:
    company, establishment = object_scope(instance)
    return has_permission(
        user,
        manifest.view_permission,
        company=company,
        establishment=establishment,
    )


def can_manage_object(user, manifest, instance) -> bool:
    company, establishment = object_scope(instance)
    return has_permission(
        user,
        manifest.manage_permission,
        company=company,
        establishment=establishment,
    )


def effective_field_view_permission(definition, manifest) -> str:
    return definition.view_permission or manifest.view_permission


def effective_field_edit_permission(definition, manifest) -> str:
    return definition.edit_permission or manifest.manage_permission


def can_view_custom_field(user, definition) -> bool:
    manifest = get_model_manifest(definition.model_key)
    return has_any_scope_permission(user, manifest.view_permission) and has_any_scope_permission(
        user,
        effective_field_view_permission(definition, manifest),
    )


def can_edit_custom_field(user, definition) -> bool:
    manifest = get_model_manifest(definition.model_key)
    return has_any_scope_permission(user, manifest.manage_permission) and has_any_scope_permission(
        user,
        effective_field_edit_permission(definition, manifest),
    )


def can_view_custom_field_on_object(user, definition, instance) -> bool:
    manifest = get_model_manifest(definition.model_key)
    company, establishment = object_scope(instance)
    return can_view_object(user, manifest, instance) and has_permission(
        user,
        effective_field_view_permission(definition, manifest),
        company=company,
        establishment=establishment,
    )


def can_edit_custom_field_on_object(user, definition, instance) -> bool:
    manifest = get_model_manifest(definition.model_key)
    company, establishment = object_scope(instance)
    return can_manage_object(user, manifest, instance) and has_permission(
        user,
        effective_field_edit_permission(definition, manifest),
        company=company,
        establishment=establishment,
    )


def validate_permission_overrides(*, manifest, view_permission: str, edit_permission: str, is_sensitive: bool) -> None:
    allowed_codes = set(
        Permission.objects.filter(
            code__in=[code for code in (view_permission, edit_permission) if code]
        ).values_list("code", flat=True)
    )
    allowed_codes.update({manifest.view_permission, manifest.manage_permission})
    for label, code in (("view_permission", view_permission), ("edit_permission", edit_permission)):
        if code and code not in allowed_codes:
            raise ValidationError({label: "Unknown permission code."})
    if is_sensitive and (not view_permission or not edit_permission):
        raise ValidationError(
            {"is_sensitive": "Sensitive custom fields require explicit view and edit permissions."}
        )
