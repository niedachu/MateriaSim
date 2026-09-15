"""Packing contracts, rigid geometry, periodic clashes and unique-molecule analysis regressions."""

import copy
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path

import numpy as np

from materiasim.engines.gromacs.parameters import collect_models, merge_types
from materiasim.scenarios.packed import validate_packing
from materiasim.analysis.component_contacts import molecule_pairs
from materiasim.storage import read_json
from materiasim.builders.packmol import check_periodic_clashes, ordered_instances, packmol_info, pdb_template, read_packed
from materiasim.specs.schema import load_spec
from materiasim.engines.gromacs.topology import atom_mapping

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


class PackingTests(unittest.TestCase):
    """Keep semantic and numeric boundary failures explicit without requiring a native simulation."""

    def setUp(self):
        """Allocate disposable negative fixtures and read existing frozen mixture models."""
        temporary = tempfile.TemporaryDirectory(prefix="packing-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.spec, self.sources, _ = load_spec(EXAMPLES / "packed_mixture_water.json")

    def test_all_new_examples_validate(self):
        """Water mixtures and dry regression are real configurations, not advertised placeholders."""
        for name in ("zil_water", "ions_water", "mixture_water", "zil_dry"):
            spec, _, _ = load_spec(EXAMPLES / f"packed_{name}.json")
            self.assertEqual(spec["scenario"]["kind"], "packed_liquid")

    def test_shared_global_parameters(self):
        """ZIL/CAT/ANI share eleven identical types and three independent molecule blocks."""
        types, models = collect_models(self.spec, self.sources)
        self.assertEqual(len(types), 11)
        self.assertEqual([len(model["template"]) for model in models.values()], [39, 33, 8])

    def test_repeated_model_regions_have_unique_ids(self):
        """The same model in separate regions retains distinct groups and molecular identities."""
        spec, sources, _ = load_spec(EXAMPLES / "packed_zil_water.json")
        _, models = collect_models(spec, sources)
        instances = ordered_instances(spec, models)
        self.assertEqual([item["group_id"] for item in instances], ["left", "right"])
        self.assertEqual([item["molecule_id"] for item in instances], ["ZIL:1", "ZIL:2"])

    def test_wrong_group_totals(self):
        """A missing molecular instance cannot be hidden in the requested total."""
        self.spec["scenario"]["groups"][0]["count"] = 2
        with self.assertRaisesRegex(ValueError, "totals differ"):
            validate_packing(self.spec, self.sources)

    def test_zero_count_rejected(self):
        """Zero-count groups fail; omission is the only way to leave a material out."""
        self.spec["scenario"]["groups"][0]["count"] = 0
        with self.assertRaisesRegex(ValueError, "integer required"):
            validate_packing(self.spec, self.sources)

    def test_duplicate_group_rejected(self):
        """Repeated group IDs cannot masquerade as separate instances."""
        self.spec["scenario"]["groups"][1]["id"] = self.spec["scenario"]["groups"][0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate group"):
            validate_packing(self.spec, self.sources)

    def test_invalid_region_rejected(self):
        """Reversed and out-of-box regions are not silently clipped."""
        self.spec["scenario"]["groups"][0]["min_nm"] = [4.5, 0, 0]
        with self.assertRaisesRegex(ValueError, "minimum must"):
            validate_packing(self.spec, self.sources)

    def test_solvent_group_identity_reserved(self):
        """A user group cannot collide with the generated water-fill mapping namespace."""
        self.spec["scenario"]["groups"][0]["id"] = "solvent_fill"
        with self.assertRaisesRegex(ValueError, "reserved solvent_fill"):
            validate_packing(self.spec, self.sources)

    def test_conflicting_type_rejected(self):
        """Equal type names with changed Lennard-Jones parameters cannot coexist."""
        table, _ = collect_models(self.spec, self.sources)
        row = list(table["o"])
        row[-1] = "9.0"
        with self.assertRaisesRegex(ValueError, "Conflicting atom type"):
            merge_types(table, [("atomtypes", row)])

    def test_macro_rejected(self):
        """Molecular preprocessing cannot silently activate an unsupported branch."""
        path = self.root / "cat.itp"
        path.write_text("#ifdef SOMETHING\n" + self.sources["cat.itp"].read_text() + "#endif\n")
        with self.assertRaisesRegex(ValueError, "without macros"):
            collect_models(self.spec, dict(self.sources, **{"cat.itp": path}))

    def test_missing_bond_parameter_rejected(self):
        """Implicit parameter lookup is not substituted for the frozen explicit GAFF bond."""
        path = self.root / "cat.itp"
        text = self.sources["cat.itp"].read_text()
        self.assertIn("191535.152000", text)
        path.write_text(text.replace("191535.152000", "", 1))
        with self.assertRaisesRegex(ValueError, "implicit bonded"):
            collect_models(self.spec, dict(self.sources, **{"cat.itp": path}))

    def test_unbalanced_charge_rejected(self):
        """Adding a charged ion requires an explicit balancing composition, never automatic ions."""
        self.spec["components"][1]["count"] = 2
        self.spec["scenario"]["groups"][1]["count"] = 2
        with self.assertRaisesRegex(ValueError, "neutral explicit"):
            validate_packing(self.spec, self.sources)

    def test_dry_pressure_coupling_rejected(self):
        """The dry regression cannot accidentally run the aqueous NPT protocol."""
        self.spec["scenario"]["solvent"] = dict(kind="none")
        with self.assertRaisesRegex(ValueError, "fixed volume"):
            validate_packing(self.spec, self.sources)

    def test_dry_hydration_rejected(self):
        """A no-water experiment cannot advertise a hydration result."""
        spec, sources, _ = load_spec(EXAMPLES / "packed_zil_dry.json")
        spec["analysis_requests"] = [dict(kind="hydration_contacts")]
        with self.assertRaisesRegex(ValueError, "cannot request hydration"):
            validate_packing(spec, sources)

    def test_missing_packmol_rejected(self):
        """Absent Packmol is a hard dependency error, not an alternate-packer fallback."""
        with self.assertRaises(FileNotFoundError):
            packmol_info("missing-native-packer-test-73129")

    def test_packmol_requires_file_input_interface(self):
        """Versions with PBC but without -i are rejected instead of piping non-seekable input."""
        with patch("materiasim.builders.packmol.shutil.which", return_value="/usr/bin/true"), \
             patch("materiasim.builders.packmol.subprocess.run", return_value=SimpleNamespace(stdout="Version 20.15.0",stderr="")):
            with self.assertRaisesRegex(ValueError, "21.1.0"):
                packmol_info()

    def test_periodic_edge_clash(self):
        """Atoms separated in Cartesian coordinates can clash through the periodic boundary."""
        atoms = [dict(molecule_id="A:1",xyz_nm=[.01,0,0]),dict(molecule_id="A:2",xyz_nm=[2.99,0,0])]
        with self.assertRaisesRegex(ValueError, "periodic inter-molecular clash"):
            check_periodic_clashes(atoms, [3,3,3], .25)

    def test_pdb_roundtrip_and_missing_atom(self):
        """The PDB adapter preserves nm scale and rejects incomplete Packmol coordinates."""
        template = [dict(name="O1",resname="ANI",xyz_nm=[.3,.4,.5])]
        instance = dict(template=template,molecule_id="ANI:1",group_id="a",group_instance_id="a:1",min_nm=[0,0,0],max_nm=[3,3,3])
        path = self.root / "packed.pdb"
        path.write_text(pdb_template(template))
        self.assertEqual(read_packed(path, [instance])[0]["xyz_nm"], [.3,.4,.5])
        with self.assertRaisesRegex(ValueError, "atom/count"):
            read_packed(path, [instance, instance])

    def test_unique_molecular_contact_not_atom_pairs(self):
        """Four atom contacts between two molecules contribute only one molecular pair."""
        box = np.array([30,30,30,90,90,90], dtype=float)
        a = np.array([[0,0,0],[.1,0,0]], dtype=float)
        b = np.array([[29.9,0,0],[29.8,0,0]], dtype=float)
        self.assertEqual(molecule_pairs(a,b,["A:1"]*2,["B:1"]*2,box,.1), {("A:1","B:1")})

    def test_same_component_excludes_internal_contacts(self):
        """Same-component pair counts exclude internal contacts and symmetric double counting."""
        p = np.array([[0,0,0],[.1,0,0],[.2,0,0]], dtype=float)
        ids = ["A:1","A:1","A:2"]
        box = np.array([30,30,30,90,90,90], dtype=float)
        self.assertEqual(molecule_pairs(p,p,ids,ids,box,.1), {("A:1","A:2")})

    def test_dry_mapping(self):
        """No-SOL mapping works only when the scenario explicitly disables solvent."""
        top = self.root / "system.top"
        top.write_text("[ moleculetype ]\nA 3\n[ atoms ]\n1 C 1 A C 1 0 12\n[ molecules ]\nA 1\n")
        gro = self.root / "system.gro"
        gro.write_text("dry\n1\n" + f"{1:5d}{'A':<5}{'C':>5}{1:5d}{0:8.3f}{0:8.3f}{0:8.3f}" + "\n3 3 3\n")
        self.assertEqual(atom_mapping(top, gro, {"A":1}, require_solvent=False)["counts"], {"A":1})
        with self.assertRaisesRegex(ValueError, "No solvent"):
            atom_mapping(top, gro, {"A":1})


if __name__ == "__main__":
    unittest.main()
