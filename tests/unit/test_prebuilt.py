"""Independent component and fixed-mixture contracts using existing CAT/ANI assets."""

import copy
import tempfile
import unittest
from pathlib import Path

from materiasim.specs.experiment import interaction_bundle, resolve_components
from materiasim.storage import read_json, write_json
from materiasim.specs.composition import declared_counts
from materiasim.engines.gromacs.prebuilt import molecular_definitions, validate_prebuilt_sources, verify_processed_models
from materiasim.workflows.validation import load_spec

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


class PrebuiltTests(unittest.TestCase):
    """Guard model coverage, independent molecules, exact counts and atom order."""

    def setUp(self):
        """Read immutable example sources and allocate isolated negative-test fixtures."""
        self.temp = tempfile.TemporaryDirectory(prefix="prebuilt-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.spec, self.sources, _ = load_spec(EXAMPLES / "cat_ani_smoke.json")

    def test_pair_has_two_real_models(self):
        """The pair is two molecular identities, not a renamed single pseudo-component."""
        self.assertEqual(declared_counts(self.spec), {"CAT": 1, "ANI": 1})
        self.assertEqual(self.spec["scenario"]["solvent_count"], 2957)
        sizes = [len([row for section, row in molecular_definitions(self.sources[item["model"]["topology"]])[item["id"]]
                      if section == "atoms"]) for item in self.spec["components"]]
        self.assertEqual(sizes, [33, 8])

    def test_duplicate_component_rejected(self):
        """Duplicate experiment IDs are rejected before duplicate assets can shadow models."""
        components = read_json(EXAMPLES / "cat_ani_smoke.json")["components"]
        components[1] = copy.deepcopy(components[0])
        with self.assertRaisesRegex(ValueError, "Duplicate component"):
            resolve_components(components, EXAMPLES, {})

    def test_incomplete_bundle_rejected(self):
        """A bundle covering only CAT cannot authorize a CAT/ANI system."""
        bundle = read_json(EXAMPLES.parent / "catalog/interaction_bundles/cat_ani_bundle.json")
        del bundle["model_hashes"]["ANI"]
        write_json(self.root / "bundle.json", bundle)
        with self.assertRaisesRegex(ValueError, "exactly all component"):
            interaction_bundle(self.root / "bundle.json", self.spec["components"], {})

    def test_count_change_is_not_assembly(self):
        """Changing count cannot reuse a fixed one-pair structure as two pairs."""
        self.spec["components"][0]["count"] = 2
        with self.assertRaisesRegex(ValueError, "composition differs"):
            validate_prebuilt_sources(self.spec, self.sources)

    def test_prebuilt_order_is_checked(self):
        """An unordered composition match cannot authorize changed coordinate order."""
        self.spec["components"].reverse()
        with self.assertRaisesRegex(ValueError, "molecule order"):
            validate_prebuilt_sources(self.spec, self.sources)

    def test_frozen_box_not_recentered(self):
        """An accepted fixed structure cannot silently receive a different declared box."""
        self.spec["scenario"]["box_nm"] = [5, 5, 5]
        with self.assertRaisesRegex(ValueError, "Frozen prebuilt box"):
            validate_prebuilt_sources(self.spec, self.sources)

    def test_cross_molecule_terms_rejected(self):
        """System-level bonded terms cannot bypass the separate frozen model definitions."""
        path = self.root / "unsafe.top"
        path.write_text(self.sources["pair_system.top"].read_text() + "\n[ intermolecular_interactions ]\n[ bonds ]\n1 34 1\n")
        with self.assertRaisesRegex(ValueError, "only include models"):
            validate_prebuilt_sources(self.spec, dict(self.sources, **{"pair_system.top": path}))

    def test_processed_bond_change_rejected(self):
        """Post-preprocessing model comparison covers bonded terms, not just atom names."""
        text = self.sources["cat.itp"].read_text() + self.sources["ani.itp"].read_text()
        path = self.root / "processed.top"
        path.write_text(text)
        verify_processed_models(self.spec, self.sources, path)
        path.write_text(text.replace("191535.152000", "191536.152000"))
        with self.assertRaisesRegex(ValueError, "Preprocessed model differs"):
            verify_processed_models(self.spec, self.sources, path)


if __name__ == "__main__":
    unittest.main()
