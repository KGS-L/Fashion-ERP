import json
from pathlib import Path

from django.test import SimpleTestCase


COMMERCIAL_ID = "LicenseRef-Ivadoo-Commercial"


class ComponentLicenseBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[3]
        map_path = self.repo_root / "docs/product/component-license-map.json"
        self.component_map = json.loads(map_path.read_text(encoding="utf-8"))

    def test_license_map_declares_expected_defaults(self):
        self.assertEqual(self.component_map["schema_version"], 1)
        self.assertEqual(self.component_map["default_license"], "LGPL-3.0-only")
        self.assertEqual(self.component_map["commercial_license"], COMMERCIAL_ID)
        commercial_notice = self.repo_root / self.component_map["commercial_license_file"]
        self.assertTrue(commercial_notice.is_file())
        self.assertIn(COMMERCIAL_ID, commercial_notice.read_text(encoding="utf-8"))

    def test_commercial_directories_have_local_markers(self):
        marker_names = ("LICENSE", "LICENSE.ivadoo-commercial", "LICENSING.md")
        for entry in self.component_map["commercial_directories"]:
            with self.subTest(path=entry["path"]):
                directory = self.repo_root / entry["path"]
                self.assertTrue(directory.is_dir())
                markers = [directory / name for name in marker_names]
                matching = [
                    marker
                    for marker in markers
                    if marker.is_file()
                    and COMMERCIAL_ID in marker.read_text(encoding="utf-8")
                ]
                self.assertTrue(
                    matching,
                    f"{entry['path']} must carry a local {COMMERCIAL_ID} marker",
                )

    def test_mixed_sales_commercial_files_are_explicitly_listed(self):
        sales_root = self.repo_root / "platform/server/ivadoo/sales"
        marker = sales_root / "LICENSING.md"
        marker_text = marker.read_text(encoding="utf-8")
        self.assertIn(COMMERCIAL_ID, marker_text)

        for entry in self.component_map["commercial_files"]:
            with self.subTest(path=entry["path"]):
                source = self.repo_root / entry["path"]
                self.assertTrue(source.is_file())
                relative = source.relative_to(sales_root).as_posix()
                self.assertIn(
                    f"`{relative}`",
                    marker_text,
                    f"{relative} must be explicitly listed in sales/LICENSING.md",
                )
