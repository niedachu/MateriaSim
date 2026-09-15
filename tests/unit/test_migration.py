"""Scientific input and package-boundary checks for the source/catalog migration."""

import unittest
from pathlib import Path
from unittest.mock import patch

from materiasim.workflows.validation import load_spec
from materiasim.storage import read_json, sha256, source_root
from materiasim.workflows.build import build

ROOT = Path(__file__).resolve().parents[2]


class MigrationTests(unittest.TestCase):
    """Require preserved source bytes and usable catalog inputs without old-case dependencies."""

    def test_asset_bytes_preserved(self):
        """Every catalog source equals its recorded original, not a regenerated approximation."""
        records = read_json(ROOT / "docs/architecture/migration_map.json")["assets"]
        for item in records:
            with self.subTest(source=item["source"]):
                self.assertEqual(sha256(ROOT / item["source"]), item["sha256"])
                self.assertEqual(sha256(ROOT / item["target"]), item["sha256"])

    def test_all_experiment_identities_unchanged(self):
        """Moving references does not change resolved scientific identities of any existing example."""
        for path in sorted((ROOT / "examples").glob("*.json")):
            with self.subTest(example=path.name):
                old, _, old_hash = load_spec(ROOT / "materials_simulation/examples" / path.name)
                new, sources, new_hash = load_spec(path)
                self.assertEqual(old_hash, new_hash)
                self.assertEqual(old, new)
                self.assertTrue(all(ROOT / "catalog" in source.parents for source in sources.values()))

    def test_build_protects_checkout(self):
        """A moved or editable-installed package still refuses generated Runs anywhere in its checkout."""
        self.assertEqual(source_root(), ROOT)
        with patch("materiasim.engines.gromacs.adapter.engine_info", return_value={}):
            with self.assertRaisesRegex(ValueError, "outside framework source"):
                build(ROOT / "examples/packed_zil_water.json", ROOT / "studies/forbidden")


if __name__ == "__main__":
    unittest.main()
