from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from fashionerp.audit.services import record_audit_event

from .models import ModuleInstallation
from .registry import dependents_of, get_module, iter_modules, module_for_api_path


def module_state(organization, module_code: str) -> dict:
    manifest = get_module(module_code)
    installation = ModuleInstallation.objects.filter(
        organization=organization,
        module_code=module_code,
    ).first()
    if installation:
        state = installation.state
        version = installation.installed_version
    else:
        state = (
            ModuleInstallation.State.ENABLED
            if manifest.required or manifest.default_enabled
            else ModuleInstallation.State.INSTALLED
        )
        version = manifest.version
    return {
        "code": manifest.code,
        "name": manifest.name,
        "version": version,
        "available_version": manifest.version,
        "state": state,
        "enabled": manifest.required or state == ModuleInstallation.State.ENABLED,
        "required": manifest.required,
        "default_enabled": manifest.default_enabled,
        "edition": manifest.edition,
        "dependencies": list(manifest.dependencies),
    }


def is_module_enabled(organization, module_code: str) -> bool:
    return bool(module_state(organization, module_code)["enabled"])


def list_module_states(organization) -> list[dict]:
    return [module_state(organization, item.code) for item in iter_modules()]


def _validate_dependencies_enabled(organization, module_code: str) -> None:
    manifest = get_module(module_code)
    missing = [
        dependency
        for dependency in manifest.dependencies
        if not is_module_enabled(organization, dependency)
    ]
    if missing:
        raise ValidationError(
            {"dependencies": f"Enable dependencies first: {', '.join(sorted(missing))}."}
        )


def _validate_no_enabled_dependents(organization, module_code: str) -> None:
    enabled_dependents = [
        item.code
        for item in dependents_of(module_code)
        if is_module_enabled(organization, item.code)
    ]
    if enabled_dependents:
        raise ValidationError(
            {
                "dependents": (
                    "Disable dependent modules first: "
                    + ", ".join(sorted(enabled_dependents))
                    + "."
                )
            }
        )


def set_module_state(
    *,
    organization,
    module_code: str,
    enabled: bool,
    actor=None,
    request=None,
) -> ModuleInstallation:
    manifest = get_module(module_code)
    if not enabled and manifest.required:
        raise ValidationError({"module": "Required modules cannot be disabled."})
    if enabled:
        _validate_dependencies_enabled(organization, module_code)
    else:
        _validate_no_enabled_dependents(organization, module_code)

    with transaction.atomic():
        installation, _ = ModuleInstallation.objects.select_for_update().get_or_create(
            organization=organization,
            module_code=module_code,
            defaults={
                "installed_version": manifest.version,
                "state": ModuleInstallation.State.INSTALLED,
                "last_changed_by": actor,
            },
        )
        before = {
            "module_code": installation.module_code,
            "installed_version": installation.installed_version,
            "state": installation.state,
        }
        installation.installed_version = manifest.version
        installation.state = (
            ModuleInstallation.State.ENABLED
            if enabled
            else ModuleInstallation.State.DISABLED
        )
        installation.last_changed_by = actor
        installation.save(
            update_fields=(
                "installed_version",
                "state",
                "last_changed_by",
                "updated_at",
            )
        )
        after = {
            "module_code": installation.module_code,
            "installed_version": installation.installed_version,
            "state": installation.state,
        }
        record_audit_event(
            organization=organization,
            actor=actor,
            action=(
                "platform.module.enable" if enabled else "platform.module.disable"
            ),
            object_instance=installation,
            before=before,
            after=after,
            request=request,
        )
        return installation


def assert_api_module_enabled(organization, path: str) -> None:
    manifest = module_for_api_path(path)
    if manifest is None or manifest.required:
        return
    if not is_module_enabled(organization, manifest.code):
        raise PermissionDenied("This FashionERP module is not enabled.")
