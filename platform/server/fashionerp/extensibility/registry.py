from dataclasses import dataclass
import re


MODULE_CODE_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,119}$")


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


_MODULES: dict[str, ModuleManifest] = {}


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
        raise LookupError(f"Unknown FashionERP module: {code}") from exc


def iter_modules() -> tuple[ModuleManifest, ...]:
    return tuple(sorted(_MODULES.values(), key=lambda item: item.code))


def dependents_of(code: str) -> tuple[ModuleManifest, ...]:
    return tuple(
        manifest
        for manifest in iter_modules()
        if code in manifest.dependencies
    )


def module_for_api_path(path: str) -> ModuleManifest | None:
    matches: list[tuple[int, ModuleManifest]] = []
    for manifest in _MODULES.values():
        for prefix in manifest.api_prefixes:
            if path.startswith(prefix):
                matches.append((len(prefix), manifest))
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]
