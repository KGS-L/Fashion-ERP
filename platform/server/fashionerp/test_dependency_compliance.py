import json
import re
import tomllib
from pathlib import Path

from django.test import SimpleTestCase


SERVER_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = SERVER_ROOT.parents[1]
PYPROJECT = SERVER_ROOT / "pyproject.toml"
LICENSE_MANIFEST = (
    REPOSITORY_ROOT / "docs" / "compliance" / "dependency-licenses.json"
)


def normalize_dependency(requirement: str) -> str:
    name = re.split(r"[<>=!~\[\s]", requirement, maxsplit=1)[0]
    return name.lower().replace("_", "-")


class DependencyComplianceTests(SimpleTestCase):
    def test_every_direct_runtime_and_build_dependency_is_reviewed(self):
        with PYPROJECT.open("rb") as handle:
            project = tomllib.load(handle)
        with LICENSE_MANIFEST.open("r", encoding="utf-8") as handle:
            reviewed = json.load(handle)

        runtime = {
            normalize_dependency(item)
            for item in project["project"]["dependencies"]
        }
        build = {
            normalize_dependency(item)
            for item in project["build-system"]["requires"]
        }
        required = runtime | build

        missing = sorted(required.difference(reviewed))
        self.assertEqual(
            missing,
            [],
            msg=f"Direct dependencies missing license review: {missing}",
        )

        unreviewed = sorted(
            name
            for name in required
            if not reviewed[name].get("reviewed", False)
        )
        self.assertEqual(
            unreviewed,
            [],
            msg=f"Direct dependencies not approved by review: {unreviewed}",
        )

    def test_reviewed_direct_licenses_are_not_unknown(self):
        with LICENSE_MANIFEST.open("r", encoding="utf-8") as handle:
            reviewed = json.load(handle)

        unknown = sorted(
            name
            for name, metadata in reviewed.items()
            if not metadata.get("license")
            or metadata["license"].lower() in {"unknown", "proprietary"}
        )
        self.assertEqual(
            unknown,
            [],
            msg=f"Dependencies with unresolved license status: {unknown}",
        )
