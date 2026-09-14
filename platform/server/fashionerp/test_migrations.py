import re

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase


FOUNDATION_APPS = {
    "identity",
    "organizations",
    "authorization",
    "audit",
    "internationalization",
}
VERSIONED_MIGRATION_NAME = re.compile(r"^\d{4}_[a-z0-9_]+$")


class FoundationMigrationContractTests(TestCase):
    def setUp(self):
        self.loader = MigrationLoader(connection, ignore_no_migrations=True)

    def test_foundation_migration_graph_has_no_conflicts(self):
        conflicts = {
            app_label: names
            for app_label, names in self.loader.detect_conflicts().items()
            if app_label in FOUNDATION_APPS
        }
        self.assertEqual(conflicts, {})

    def test_each_foundation_app_has_one_linear_leaf(self):
        leaves_by_app = {
            app_label: [
                node
                for node in self.loader.graph.leaf_nodes(app_label)
                if node[0] == app_label
            ]
            for app_label in FOUNDATION_APPS
        }

        for app_label, leaves in leaves_by_app.items():
            with self.subTest(app_label=app_label):
                self.assertEqual(
                    len(leaves),
                    1,
                    msg=(
                        f"{app_label} must have one migration leaf; "
                        f"found {leaves}"
                    ),
                )

    def test_foundation_migrations_use_explicit_numeric_versions(self):
        for (app_label, migration_name) in self.loader.disk_migrations:
            if app_label not in FOUNDATION_APPS:
                continue
            with self.subTest(
                app_label=app_label,
                migration_name=migration_name,
            ):
                self.assertRegex(
                    migration_name,
                    VERSIONED_MIGRATION_NAME,
                )

    def test_foundation_operations_declare_a_reverse_path(self):
        irreversible = []
        for key, migration in self.loader.disk_migrations.items():
            app_label, migration_name = key
            if app_label not in FOUNDATION_APPS:
                continue
            for index, operation in enumerate(migration.operations):
                if not getattr(operation, "reversible", True):
                    irreversible.append(
                        f"{app_label}.{migration_name}[{index}] "
                        f"{operation.__class__.__name__}"
                    )

        self.assertEqual(
            irreversible,
            [],
            msg=(
                "Foundation migrations contain irreversible operations. "
                "Document a restore-only migration explicitly before adding "
                f"one: {irreversible}"
            ),
        )
