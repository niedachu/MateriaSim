from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FragmentConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(
            (PROJECT_ROOT / "parameterization" / "fragment_config.json").read_text(
                encoding="utf-8"
            )
        )

    def test_two_named_cap_schemes(self) -> None:
        self.assertEqual(set(self.config["schemes"]), {"methyl", "ethyl"})

    def test_each_scheme_has_three_charge_balanced_fragments(self) -> None:
        for scheme in self.config["schemes"].values():
            fragments = scheme["fragments"]
            self.assertEqual(set(fragments), {"sulfonate", "imidazolium", "ether"})
            self.assertEqual(
                sum(int(fragment["formal_charge_e"]) for fragment in fragments.values()),
                int(self.config["target"]["formal_charge_e"]),
            )

    def test_retained_heavy_atoms_cover_target_once(self) -> None:
        expected = list(range(1, 20))
        for scheme in self.config["schemes"].values():
            retained = sorted(
                atom_map
                for fragment in scheme["fragments"].values()
                for atom_map in fragment["retained_atom_maps"]
            )
            self.assertEqual(retained, expected)

    def test_cap_maps_do_not_overlap_retained_maps(self) -> None:
        for scheme in self.config["schemes"].values():
            for fragment in scheme["fragments"].values():
                retained = set(fragment["retained_atom_maps"])
                caps = {
                    atom_map
                    for group in fragment["cap_groups_atom_maps"]
                    for atom_map in group
                }
                self.assertTrue(caps)
                self.assertTrue(all(atom_map >= 900 for atom_map in caps))
                self.assertFalse(retained & caps)

    def test_cut_bonds_are_expected_nonpolar_boundaries(self) -> None:
        self.assertEqual(self.config["cut_bonds_target_zero_based"], [[3, 4], [8, 9]])

    def test_qm_and_resp_protocol_is_fixed(self) -> None:
        self.assertEqual(
            self.config["qm"],
            {
                "method": "hf",
                "basis": "6-31g*",
                "geometry_convergence": "gau_tight",
                "gas_phase": True,
            },
        )
        self.assertEqual(self.config["resp"]["stages"], 2)
        self.assertEqual(self.config["resp"]["constrain_each_cap_group_charge_e"], 0.0)

    def test_formal_atom_and_charge_invariants(self) -> None:
        self.assertEqual(self.config["target"]["expected_atom_count_with_hydrogens"], 39)
        self.assertEqual(self.config["target"]["formal_charge_e"], 0)
        self.assertEqual(self.config["target"]["multiplicity"], 1)


if __name__ == "__main__":
    unittest.main()
