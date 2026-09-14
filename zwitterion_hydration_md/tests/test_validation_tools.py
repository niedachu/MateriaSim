from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.crosscheck_counts import compare_counts, read_gromacs_xvg, read_mdanalysis_csv
from parameterization.scripts.validate_parameters import (
    parse_itp_atoms,
    parse_mol2_atoms,
    summarize_atomic_charges,
    validate_atom_table,
)
from parameterization.scripts.prepare_gaff2_am1bcc import neutralize_mol2


class ParameterValidationTests(unittest.TestCase):
    def test_mol2_and_itp_charge_and_order(self) -> None:
        mol2_text = """@<TRIPOS>MOLECULE
ZIL
2 1 1 0 0
SMALL
USER_CHARGES

@<TRIPOS>ATOM
1 A1 0.0 0.0 0.0 c3 1 ZIL 0.500000
2 A2 1.0 0.0 0.0 o  1 ZIL -0.500000
@<TRIPOS>BOND
1 1 2 1
"""
        itp_text = """[ moleculetype ]
ZIL 3

[ atoms ]
1 c3 1 ZIL A1 1 0.500000 12.011
2 o  1 ZIL A2 2 -0.500000 15.999
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            mol2 = temp / "zil.mol2"
            itp = temp / "zil.itp"
            mol2.write_text(mol2_text, encoding="utf-8")
            itp.write_text(itp_text, encoding="utf-8")
            mol2_atoms = parse_mol2_atoms(mol2)
            itp_atoms = parse_itp_atoms(itp)
        self.assertEqual(validate_atom_table(mol2_atoms, 0.0, 1e-4)["total_charge_e"], 0.0)
        self.assertEqual(validate_atom_table(itp_atoms, 0.0, 1e-4)["total_charge_e"], 0.0)
        self.assertEqual([atom["name"] for atom in mol2_atoms], [atom["name"] for atom in itp_atoms])

    def test_non_neutral_table_is_rejected(self) -> None:
        atoms = [{"index": 1, "name": "A1", "atom_type": "c3", "charge": 0.1}]
        with self.assertRaises(ValueError):
            validate_atom_table(atoms, 0.0, 1e-4)

    def test_small_am1bcc_residual_is_neutralized(self) -> None:
        mol2_text = """@<TRIPOS>MOLECULE
ZIL
2 1 1 0 0
SMALL
USER_CHARGES

@<TRIPOS>ATOM
1 A1 0.0 0.0 0.0 c3 1 ZIL 0.498000
2 A2 1.0 0.0 0.0 o  1 ZIL -0.502000
@<TRIPOS>BOND
1 1 2 1
@<TRIPOS>SUBSTRUCTURE
1 ZIL 1 TEMP 0 **** **** 0 ROOT
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            raw = temp / "raw.mol2"
            neutral = temp / "neutral.mol2"
            raw.write_text(mol2_text, encoding="utf-8")
            report = neutralize_mol2(raw, neutral)
            total = sum(float(atom["charge"]) for atom in parse_mol2_atoms(neutral))
        self.assertAlmostEqual(report["original_total_charge_e"], -0.004, places=6)
        self.assertLess(abs(total), 1e-4)

    def test_large_am1bcc_residual_is_rejected(self) -> None:
        mol2_text = """@<TRIPOS>MOLECULE
ZIL
2 1 1 0 0
SMALL
USER_CHARGES

@<TRIPOS>ATOM
1 A1 0.0 0.0 0.0 c3 1 ZIL 0.400000
2 A2 1.0 0.0 0.0 o  1 ZIL -0.500000
@<TRIPOS>BOND
1 1 2 1
@<TRIPOS>SUBSTRUCTURE
1 ZIL 1 TEMP 0 **** **** 0 ROOT
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            raw = temp / "raw.mol2"
            raw.write_text(mol2_text, encoding="utf-8")
            with self.assertRaises(ValueError):
                neutralize_mol2(raw, temp / "neutral.mol2")

    def test_atomic_charge_screen_passes_reasonable_neutral_set(self) -> None:
        report = summarize_atomic_charges([0.8, -0.8], 0.0, 1e-4, 2.0)
        self.assertTrue(report["passed_conservative_magnitude_screen"])
        self.assertEqual(report["atoms_exceeding_absolute_limit"], 0)

    def test_atomic_charge_screen_flags_extreme_neutral_set(self) -> None:
        report = summarize_atomic_charges([6.65, -6.65], 0.0, 1e-4, 2.0)
        self.assertFalse(report["passed_conservative_magnitude_screen"])
        self.assertEqual(report["atoms_exceeding_absolute_limit"], 2)


class CrosscheckTests(unittest.TestCase):
    def test_equal_frame_counts_pass(self) -> None:
        report = compare_counts({0.0: 8, 2.0: 9}, {0.0: 8, 2.0: 9}, 1e-3)
        self.assertEqual(report["matched_frames"], 2)
        self.assertEqual(report["mismatch_count"], 0)

    def test_mismatch_is_reported(self) -> None:
        report = compare_counts({0.0: 8}, {0.0: 9}, 1e-3)
        self.assertEqual(report["mismatch_count"], 1)

    def test_xvg_and_csv_parsers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            xvg = temp / "gmx.xvg"
            csv_path = temp / "mda.csv"
            xvg.write_text("# comment\n@ metadata\n0.0 8\n2.0 9\n", encoding="utf-8")
            csv_path.write_text("frame,time_ps,total_unique_count\n0,0.0,8\n1,2.0,9\n", encoding="utf-8")
            self.assertEqual(read_gromacs_xvg(xvg), {0.0: 8, 2.0: 9})
            self.assertEqual(read_mdanalysis_csv(csv_path), {0.0: 8, 2.0: 9})


if __name__ == "__main__":
    unittest.main()
