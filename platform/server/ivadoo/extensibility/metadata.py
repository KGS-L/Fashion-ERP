import hashlib
import json

from django.db import models

from ivadoo.authorization.services import has_any_scope_permission

from .custom_fields import active_custom_fields
from .registry import get_module, iter_model_manifests, resolve_django_model
from .security import can_edit_custom_field, can_view_custom_field
from .services import is_module_enabled


def _api_field_name(field) -> str:
    return f"{field.name}_id" if getattr(field, "many_to_one", False) else field.name


def _native_field_type(field) -> str:
    if isinstance(field, models.ForeignKey):
        return "reference"
    if isinstance(field, models.BooleanField):
        return "boolean"
    if isinstance(field, models.DateTimeField):
        return "datetime"
    if isinstance(field, models.DateField):
        return "date"
    if isinstance(field, models.DecimalField):
        return "decimal"
    if isinstance(field, (models.IntegerField, models.AutoField, models.BigAutoField)):
        return "integer"
    if isinstance(field, models.UUIDField):
        return "uuid"
    if isinstance(field, models.EmailField):
        return "email"
    if isinstance(field, models.TextField):
        return "long_text"
    if isinstance(field, models.JSONField):
        return "json"
    return "text"


def _native_field_metadata(field, manifest) -> dict:
    key = _api_field_name(field)
    choices = [
        {"value": value, "label": str(label)}
        for value, label in (field.flatchoices or [])
    ] if getattr(field, "choices", None) else []
    payload = {
        "key": key,
        "label": str(getattr(field, "verbose_name", key)).replace("_", " ").strip().title(),
        "type": _native_field_type(field),
        "native": True,
        "custom": False,
        "protected": key in manifest.protected_fields or field.name in manifest.protected_fields,
        "required": bool(
            not getattr(field, "null", False)
            and not getattr(field, "blank", False)
            and not field.has_default()
            and not getattr(field, "auto_created", False)
            and not getattr(field, "primary_key", False)
        ),
        "read_only": bool(
            getattr(field, "primary_key", False)
            or getattr(field, "auto_created", False)
            or not getattr(field, "editable", True)
        ),
        "choices": choices,
    }
    if isinstance(field, models.ForeignKey):
        payload["reference_model"] = field.remote_field.model._meta.label_lower
    return payload


def _custom_field_metadata(user, definition) -> dict:
    payload = {
        "key": definition.key,
        "label": definition.label,
        "type": definition.field_type,
        "native": False,
        "custom": True,
        "protected": False,
        "required": definition.required,
        "read_only": not can_edit_custom_field(user, definition),
        "choices": definition.options if definition.field_type in {"selection", "multi_selection"} else [],
        "searchable": definition.is_searchable,
        "reportable": definition.is_reportable,
        "sensitive": definition.is_sensitive,
        "version": definition.version,
    }
    if definition.field_type == "reference":
        payload["reference_model"] = definition.validation.get("target_model")
    return payload


def can_view_model(user, manifest) -> bool:
    return is_module_enabled(user.organization, manifest.module_code) and has_any_scope_permission(
        user,
        manifest.view_permission,
    )


def model_metadata(user, manifest) -> dict:
    model = resolve_django_model(manifest)
    native_fields = [
        _native_field_metadata(field, manifest)
        for field in model._meta.get_fields()
        if getattr(field, "concrete", False)
        and not getattr(field, "auto_created", False)
        and not getattr(field, "many_to_many", False)
    ]
    custom_fields = [
        _custom_field_metadata(user, definition)
        for definition in active_custom_fields(user.organization, manifest.key)
        if can_view_custom_field(user, definition)
    ]
    module = get_module(manifest.module_code)
    return {
        "key": manifest.key,
        "label": manifest.label,
        "module": {
            "code": module.code,
            "version": module.version,
        },
        "permissions": {
            "view": manifest.view_permission,
            "manage": manifest.manage_permission,
            "can_manage": has_any_scope_permission(user, manifest.manage_permission),
        },
        "capabilities": {
            "custom_fields": True,
            "import": manifest.importable,
            "export": manifest.exportable,
        },
        "actions": list(manifest.actions),
        "fields": sorted(native_fields + custom_fields, key=lambda item: item["key"]),
    }


def visible_model_metadata(user) -> list[dict]:
    return [
        model_metadata(user, manifest)
        for manifest in iter_model_manifests()
        if can_view_model(user, manifest)
    ]


def metadata_etag(payload) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return '"' + hashlib.sha256(encoded).hexdigest() + '"'
