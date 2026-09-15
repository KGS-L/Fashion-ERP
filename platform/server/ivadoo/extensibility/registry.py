from dataclasses import dataclass
import re

from django.apps import apps


MODULE_CODE_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,119}$")
MODEL_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,159}$")


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    code: str
    name: str
    version: str
    dependencies: tuple[str, ...] = ()
    required: bool = False
    default_enabled: bool = False
    edition: str = "community"
    api_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelManifest:
    key: str
    label: str
    django_model: str
    module_code: str
    view_permission: str
    manage_permission: str
    importable: bool = False
    exportable: bool = False
    protected_fields: frozenset[str] = frozenset()
    actions: tuple[str, ...] = ()


_MODULES: dict[str, ModuleManifest] = {}
_MODELS: dict[str, ModelManifest] = {}


def register_module(manifest: ModuleManifest) -> ModuleManifest:
    if not MODULE_CODE_RE.fullmatch(manifest.code):
        raise ValueError(f"Invalid module code: {manifest.code!r}")
    if manifest.code in manifest.dependencies:
        raise ValueError(f"Module {manifest.code!r} cannot depend on itself.")
    existing = _MODULES.get(manifest.code)
    if existing and existing != manifest:
        raise ValueError(f"Module {manifest.code!r} is already registered differently.")
    _MODULES[manifest.code] = manifest
    return manifest


def get_module(code: str) -> ModuleManifest:
    try:
        return _MODULES[code]
    except KeyError as exc:
        raise LookupError(f"Unknown Ivadoo module: {code}") from exc


def iter_modules() -> tuple[ModuleManifest, ...]:
    return tuple(sorted(_MODULES.values(), key=lambda item: item.code))


def dependents_of(code: str) -> tuple[ModuleManifest, ...]:
    return tuple(manifest for manifest in iter_modules() if code in manifest.dependencies)


def module_for_api_path(path: str) -> ModuleManifest | None:
    matches: list[tuple[int, ModuleManifest]] = []
    for manifest in _MODULES.values():
        for prefix in manifest.api_prefixes:
            if path.startswith(prefix):
                matches.append((len(prefix), manifest))
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]


def register_model(manifest: ModelManifest) -> ModelManifest:
    if not MODEL_KEY_RE.fullmatch(manifest.key):
        raise ValueError(f"Invalid model key: {manifest.key!r}")
    get_module(manifest.module_code)
    existing = _MODELS.get(manifest.key)
    if existing and existing != manifest:
        raise ValueError(f"Model {manifest.key!r} is already registered differently.")
    _MODELS[manifest.key] = manifest
    return manifest


def get_model_manifest(key: str) -> ModelManifest:
    try:
        return _MODELS[key]
    except KeyError as exc:
        raise LookupError(f"Unknown extensible model: {key}") from exc


def iter_model_manifests() -> tuple[ModelManifest, ...]:
    return tuple(sorted(_MODELS.values(), key=lambda item: item.key))


def replace_model_manifest(key: str, **changes) -> ModelManifest:
    current = get_model_manifest(key)
    values = {
        field: getattr(current, field)
        for field in current.__dataclass_fields__
    }
    values.update(changes)
    updated = ModelManifest(**values)
    _MODELS[key] = updated
    return updated


def resolve_django_model(manifest_or_key):
    manifest = get_model_manifest(manifest_or_key) if isinstance(manifest_or_key, str) else manifest_or_key
    app_label, model_name = manifest.django_model.split(".", 1)
    model = apps.get_model(app_label, model_name)
    if model is None:
        raise LookupError(f"Django model is unavailable: {manifest.django_model}")
    return model


def native_api_field_names(manifest_or_key) -> set[str]:
    model = resolve_django_model(manifest_or_key)
    names: set[str] = set()
    for field in model._meta.get_fields():
        if not getattr(field, "concrete", False) or getattr(field, "auto_created", False):
            continue
        if getattr(field, "many_to_many", False):
            continue
        names.add(f"{field.name}_id" if getattr(field, "many_to_one", False) else field.name)
    return names
