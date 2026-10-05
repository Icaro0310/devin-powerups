#!/usr/bin/env python3
"""Tests for new-repo.py — synthetic template + registry fixtures only.

The real ``new-repo.py`` filename contains a hyphen, so it is loaded via
importlib. ``_git_init`` is mocked (no git needed) and the template /
ecosystem root / registry are pointed at tmp dirs — nothing outside the
tmp dir is touched. The real ``registry.schema.json`` is used as the
validation contract (read-only).

Run:
    python tools/test_new_repo.py
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
SCHEMA = TOOLS.parent / "registry.schema.json"

_spec = importlib.util.spec_from_file_location(
    "new_repo", TOOLS / "new-repo.py"
)
new_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(new_repo)


def write_template(root: Path) -> Path:
    """A minimal synthetic template with the three placeholders."""
    template = root / "template"
    (template / "src" / "devin_template").mkdir(parents=True)
    (template / "tests").mkdir()
    (template / "pyproject.toml").write_text(
        'name = "devin-{{name}}"\ndescription = "{{description}}"\n',
        encoding="utf-8",
    )
    (template / "src" / "devin_template" / "__init__.py").write_text(
        '"""devin_template — {{description}}"""\n', encoding="utf-8"
    )
    (template / "README.md").write_text(
        "# devin-{{name}}\nmodule: devin_{{module}}\n", encoding="utf-8"
    )
    (template / "README.windows.md").write_text("Windows: {{name}}\n", encoding="utf-8")
    (template / "README.linux.md").write_text("Linux: {{name}}\n", encoding="utf-8")
    (template / "README.macos.md").write_text("macOS: planned\n", encoding="utf-8")
    (template / "tests" / "test_smoke.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    return template


def write_registry(root: Path, repositories=None) -> Path:
    if repositories is None:
        repositories = [
            {
                "name": "devin-powerups",
                "url": "https://github.com/TestOwner/devin-powerups",
                "kind": "infra",
                "visibility": "private",
                "wave": 0,
                "status": "active",
                "description": "Synthetic hub entry.",
            }
        ]
    path = root / "registry.json"
    path.write_text(
        json.dumps(
            {
                "$schema": "registry.schema.json",
                "version": 6,
                "generated": "2026-01-01",
                "owner": "TestOwner",
                "repositories": repositories,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


class NewRepoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ecosystem = root / "eco"
        self.ecosystem.mkdir()
        self.template = write_template(root)
        self.registry = write_registry(root)
        self._patches = [
            mock.patch.object(new_repo, "ECOSYSTEM", self.ecosystem),
            mock.patch.object(new_repo, "TEMPLATE", self.template),
            mock.patch.object(new_repo, "_git_init", lambda dest: None),
        ]
        for patch in self._patches:
            patch.start()

    def tearDown(self):
        for patch in self._patches:
            patch.stop()
        self._tmp.cleanup()

    def argv(self, *extra):
        return [
            *extra,
            "--registry", str(self.registry),
            "--schema", str(SCHEMA),
        ]

    def dest(self, name="alpha"):
        return self.ecosystem / f"devin-{name}"

    # -- dry-run ---------------------------------------------------------

    def test_dry_run_creates_nothing(self):
        before = self.registry.read_bytes()
        rc = new_repo.main(self.argv("--dry-run", "alpha", "Alpha tool"))
        self.assertEqual(rc, 0)
        self.assertFalse(self.dest().exists())
        self.assertEqual(self.registry.read_bytes(), before)

    def test_dry_run_still_validates(self):
        # a registry that cannot merge (missing 'repositories') fails even
        # under --dry-run, with zero side effects
        self.registry.write_text('{"owner": "TestOwner"}', encoding="utf-8")
        rc = new_repo.main(self.argv("--dry-run", "alpha", "Alpha tool"))
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.dest().exists())

    # -- scaffold + register ----------------------------------------------

    def test_scaffolds_fills_placeholders_and_registers(self):
        rc = new_repo.main(self.argv("alpha", "Alpha tool"))
        self.assertEqual(rc, 0)
        dest = self.dest()
        self.assertTrue((dest / "pyproject.toml").is_file())
        pyproject = (dest / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('name = "devin-alpha"', pyproject)
        self.assertIn('description = "Alpha tool"', pyproject)
        # devin_template dir renamed to devin_alpha
        self.assertTrue(
            (dest / "src" / "devin_alpha" / "__init__.py").is_file()
        )
        self.assertIn(
            "devin_alpha",
            (dest / "README.md").read_text(encoding="utf-8"),
        )
        self.assertTrue((dest / "README.windows.md").is_file())
        self.assertTrue((dest / "README.linux.md").is_file())
        self.assertTrue((dest / "README.macos.md").is_file())

        registry = json.loads(self.registry.read_text(encoding="utf-8"))
        entry = registry["repositories"][-1]
        self.assertEqual(entry["name"], "devin-alpha")
        self.assertEqual(
            entry["url"], "https://github.com/TestOwner/devin-alpha"
        )
        self.assertEqual(entry["kind"], "project")
        self.assertEqual(entry["visibility"], "public")
        self.assertEqual(entry["status"], "active")
        self.assertEqual(entry["description"], "Alpha tool")
        self.assertEqual(registry["generated"], new_repo.date.today().isoformat())

    def test_registered_document_validates(self):
        self.assertEqual(new_repo.main(self.argv("alpha", "Alpha tool")), 0)
        import sys

        sys.path.insert(0, str(TOOLS))
        import validate_registry

        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        merged = json.loads(self.registry.read_text(encoding="utf-8"))
        self.assertEqual(validate_registry.validate(merged, schema), [])

    def test_devin_prefix_in_name_is_stripped(self):
        rc = new_repo.main(self.argv("devin-beta", "Beta tool"))
        self.assertEqual(rc, 0)
        self.assertTrue((self.ecosystem / "devin-beta").is_dir())
        entry = json.loads(self.registry.read_text(encoding="utf-8"))[
            "repositories"
        ][-1]
        self.assertEqual(entry["name"], "devin-beta")

    # -- failure paths -----------------------------------------------------

    def test_no_register_leaves_registry_untouched(self):
        before = self.registry.read_bytes()
        rc = new_repo.main(
            self.argv("--no-register", "alpha", "Alpha tool")
        )
        self.assertEqual(rc, 0)
        self.assertTrue(self.dest().is_dir())
        self.assertEqual(self.registry.read_bytes(), before)

    def test_duplicate_registry_name_fails_before_scaffold(self):
        write_registry(
            self.registry.parent,
            repositories=[
                {
                    "name": "devin-alpha",
                    "url": "https://github.com/TestOwner/devin-alpha",
                    "kind": "project",
                    "visibility": "public",
                    "wave": 1,
                    "status": "delivered",
                    "description": "already there",
                }
            ],
        )
        rc = new_repo.main(self.argv("alpha", "Alpha tool"))
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.dest().exists())

    def test_invalid_merged_registry_fails_before_scaffold(self):
        # pre-existing entry violates the schema (visibility not in enum) —
        # the merged document can never validate, so nothing may be created
        write_registry(
            self.registry.parent,
            repositories=[
                {
                    "name": "devin-broken",
                    "url": "https://github.com/TestOwner/devin-broken",
                    "kind": "project",
                    "visibility": "pub",
                    "wave": 0,
                    "status": "active",
                    "description": "invalid",
                }
            ],
        )
        before = self.registry.read_bytes()
        rc = new_repo.main(self.argv("alpha", "Alpha tool"))
        self.assertEqual(rc, 1)
        self.assertFalse(self.dest().exists())
        self.assertEqual(self.registry.read_bytes(), before)

    def test_bad_name_rejected(self):
        for bad in ("Bad Name", "a_b", "x/y", ""):
            self.assertEqual(
                new_repo.main(self.argv(bad, "desc")), 1, msg=bad
            )
        self.assertEqual(list(self.ecosystem.iterdir()), [])

    def test_existing_dest_rejected(self):
        self.dest().mkdir(parents=True)
        self.assertEqual(new_repo.main(self.argv("alpha", "d")), 2)

    def test_git_failure_leaves_registry_untouched(self):
        before = self.registry.read_bytes()

        def boom(dest):
            raise new_repo.subprocess.CalledProcessError(1, "git")

        with mock.patch.object(new_repo, "_git_init", boom):
            rc = new_repo.main(self.argv("alpha", "Alpha tool"))
        self.assertEqual(rc, 1)
        self.assertEqual(self.registry.read_bytes(), before)

    def test_private_system_entry(self):
        rc = new_repo.main(
            self.argv(
                "--kind", "system", "--visibility", "private",
                "--wave", "3", "agent-sys", "Private runtime",
            )
        )
        self.assertEqual(rc, 0)
        entry = json.loads(self.registry.read_text(encoding="utf-8"))[
            "repositories"
        ][-1]
        self.assertEqual(entry["kind"], "system")
        self.assertEqual(entry["visibility"], "private")
        self.assertEqual(entry["wave"], 3)


if __name__ == "__main__":
    unittest.main()
