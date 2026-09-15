from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction

from ivadoo.audit.services import record_audit_event
from ivadoo.authorization.services import has_permission

from .models import CustomFieldDefinition, CustomObjectData
from .registry import (
    get_model_manifest,
    native_api_field_names,
    resolve_django_model,
)
from .security import (
    can_edit_custom_field_on_object,
    can_view_custom_field_on_object,
    validate_permission_overrides,
)
from .services import is_module_enabled


CUSTOM_FIELD_KEY_RE = re.compile(r"^x_[a-z][a-z0-9_]{1,61}$")


def validate_custom_field_definition(
    *,
    organization,
    model_key: str,
    key: str,
    field_type: str,
    options,
    validation,
    view_permission: str = "",
    edit_permission: str = "",
    is_sensitive: bool = False,
) -> None:
    manifest = get_model_manifest(model_key)
    if not is_module_enabled(organization, manifest.module_code):
        raise ValidationError({"model_key": "The target module is not enabled."})
    if not key or not CUSTOM_FIELD_KEY_RE.fullmatch(key):
        raise ValidationError(
            {"key": "Custom field keys must start with x_ and use lowercase letters, numbers and underscores."}
        )
    if key in native_api_field_names(manifest):
        raise ValidationError({"key": "A custom field cannot replace a native field."})
    if key in manifest.protected_fields:
        raise ValidationError({"key": "This key is reserved by a protected system field."})
    if field_type not in CustomFieldDefinition.FieldType.values:
        raise ValidationError({"field_type": "Unsupported custom field type."})
    if field_type in {
        CustomFieldDefinition.FieldType.SELECTION,
        CustomFieldDefinition.FieldType.MULTI_SELECTION,
    }:
        if not isinstance(options, list) or not options:
            raise ValidationError({"options": "Selection fields require a non-empty list of options."})
        normalized = [item.get("value") if isinstance(item, dict) else item for item in options]
        if any(item in (None, "") for item in normalized) or len(set(map(str, normalized))) != len(normalized):
            raise ValidationError({"options": "Selection option values must be unique and non-empty."})
    elif options not in (None, [], {}):
        raise ValidationError({"options": "Options are only supported for selection fields."})

    if field_type == CustomFieldDefinition.FieldType.REFERENCE:
        target_model = (validation or {}).get("target_model")
        if not target_model:
            raise ValidationError({"validation": "Reference fields require validation.target_model."})
        get_model_manifest(target_model)

    validate_permission_overrides(
        manifest=manifest,
        view_permission=view_permission,
        edit_permission=edit_permission,
        is_sensitive=is_sensitive,
    )


def active_custom_fields(organization, model_key: str):
    return CustomFieldDefinition.objects.filter(
        organization=organization,
        model_key=model_key,
        is_active=True,
    ).order_by("key")


def _allowed_selection_values(definition: CustomFieldDefinition) -> set[str]:
    return {
        str(item.get("value") if isinstance(item, dict) else item)
        for item in definition.options
    }


def _normalize_value(definition: CustomFieldDefinition, value, organization):
    if value in (None, ""):
        if definition.required:
            raise ValidationError({definition.key: "This custom field is required."})
        return None

    field_type = definition.field_type
    if field_type in {
        CustomFieldDefinition.FieldType.TEXT,
        CustomFieldDefinition.FieldType.LONG_TEXT,
    }:
        return str(value)
    if field_type == CustomFieldDefinition.FieldType.INTEGER:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError({definition.key: "Expected an integer."}) from exc
    if field_type == CustomFieldDefinition.FieldType.DECIMAL:
        try:
            return str(Decimal(str(value)))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError({definition.key: "Expected a decimal number."}) from exc
    if field_type == CustomFieldDefinition.FieldType.BOOLEAN:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
        raise ValidationError({definition.key: "Expected a boolean value."})
    if field_type == CustomFieldDefinition.FieldType.DATE:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError as exc:
            raise ValidationError({definition.key: "Expected an ISO date."}) from exc
    if field_type == CustomFieldDefinition.FieldType.DATETIME:
        if isinstance(value, datetime):
            return value.isoformat()
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
        except ValueError as exc:
            raise ValidationError({definition.key: "Expected an ISO datetime."}) from exc
    if field_type == CustomFieldDefinition.FieldType.SELECTION:
        text = str(value)
        if text not in _allowed_selection_values(definition):
            raise ValidationError({definition.key: "Value is not an allowed option."})
        return text
    if field_type == CustomFieldDefinition.FieldType.MULTI_SELECTION:
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        if not isinstance(value, list):
            raise ValidationError({definition.key: "Expected a list of option values."})
        allowed = _allowed_selection_values(definition)
        values = [str(item) for item in value]
        if any(item not in allowed for item in values):
            raise ValidationError({definition.key: "One or more values are not allowed options."})
        return values
    if field_type == CustomFieldDefinition.FieldType.REFERENCE:
        try:
            target_id = UUID(str(value))
        except (TypeError, ValueError) as exc:
            raise ValidationError({definition.key: "Expected a UUID reference."}) from exc
        target_key = definition.validation.get("target_model")
        target_manifest = get_model_manifest(target_key)
        target_model = resolve_django_model(target_manifest)
        queryset = target_model.objects.filter(pk=target_id)
        has_org_field = any(
            field.name == "organization"
            for field in target_model._meta.get_fields()
            if getattr(field, "concrete", False)
        )
        if has_org_field:
            queryset = queryset.filter(organization_id=organization.id)
        if not queryset.exists():
            raise ValidationError({definition.key: "Referenced object is unavailable in this organization."})
        return str(target_id)
    raise ValidationError({definition.key: "Unsupported custom field type."})


def normalize_custom_values(*, organization, model_key: str, values: dict, partial: bool = True, actor=None, target=None) -> dict:
    if not isinstance(values, dict):
        raise ValidationError({"custom": "Custom values must be an object."})
    definitions = {
        item.key: item
        for item in active_custom_fields(organization, model_key)
    }
    unknown = sorted(set(values) - set(definitions))
    if unknown:
        raise ValidationError({"custom": f"Unknown or inactive custom fields: {', '.join(unknown)}."})
    if actor is not None and target is not None:
        forbidden = [
            key for key in values
            if not can_edit_custom_field_on_object(actor, definitions[key], target)
        ]
        if forbidden:
            raise ValidationError({"custom": f"Not allowed to edit fields: {', '.join(sorted(forbidden))}."})
    normalized = {
        key: _normalize_value(definitions[key], value, organization)
        for key, value in values.items()
    }
    if not partial:
        for key, definition in definitions.items():
            if key not in normalized:
                value = definition.default_value
                normalized[key] = _normalize_value(definition, value, organization)
    return normalized


def resolve_customizable_object(*, organization, model_key: str, object_id):
    manifest = get_model_manifest(model_key)
    model = resolve_django_model(manifest)
    queryset = model.objects.filter(pk=object_id)
    has_org_field = any(
        field.name == "organization"
        for field in model._meta.get_fields()
        if getattr(field, "concrete", False)
    )
    if has_org_field:
        queryset = queryset.filter(organization_id=organization.id)
    obj = queryset.first()
    if obj is None:
        raise ValidationError({"object_id": "Target object is unavailable in this organization."})
    return obj


def visible_custom_values(*, user, model_key: str, object_id) -> dict:
    target = resolve_customizable_object(
        organization=user.organization,
        model_key=model_key,
        object_id=object_id,
    )
    manifest = get_model_manifest(model_key)
    company = getattr(target, "company", None)
    establishment = getattr(target, "establishment", None)
    if not has_permission(
        user,
        manifest.view_permission,
        company=company,
        establishment=establishment,
    ):
        raise ValidationError({"object_id": "Target object is unavailable in this scope."})
    record = CustomObjectData.objects.filter(
        organization=user.organization,
        model_key=model_key,
        object_id=object_id,
    ).first()
    stored = record.values if record else {}
    return {
        definition.key: stored.get(definition.key, definition.default_value)
        for definition in active_custom_fields(user.organization, model_key)
        if can_view_custom_field_on_object(user, definition, target)
    }


def save_custom_values(
    *,
    organization,
    model_key: str,
    object_id,
    values: dict,
    actor=None,
    request=None,
    partial: bool = True,
) -> CustomObjectData:
    target = resolve_customizable_object(
        organization=organization,
        model_key=model_key,
        object_id=object_id,
    )
    normalized = normalize_custom_values(
        organization=organization,
        model_key=model_key,
        values=values,
        partial=partial,
        actor=actor,
        target=target,
    )
    with transaction.atomic():
        record, _ = CustomObjectData.objects.select_for_update().get_or_create(
            organization=organization,
            model_key=model_key,
            object_id=object_id,
            defaults={"values": {}, "updated_by": actor, "version": 0},
        )
        before = dict(record.values)
        merged = dict(record.values) if partial else {}
        merged.update(normalized)
        record.values = merged
        record.version += 1
        record.updated_by = actor
        record.save(update_fields=("values", "version", "updated_by", "updated_at"))
        record_audit_event(
            organization=organization,
            actor=actor,
            action="platform.custom_data.update",
            object_instance=record,
            before={"values": before},
            after={"values": record.values},
            request=request,
        )
        return record
