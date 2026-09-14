from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_production import resolve_gmx, run_replicate, validate_protocol


def parse_mdp(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split(";", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().lower()] = value.strip()
    return values


class ProjectConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(
            (PROJECT_ROOT / "config" / "simulation_config.json").read_text(encoding="utf-8")
        )

    def test_zwitterion_is_net_neutral(self) -> None:
        self.assertEqual(self.config["solute"]["formal_net_charge_e"], 0)
        self.assertFalse(self.config["solvent"]["add_salt"])
        self.assertFalse(self.config["solvent"]["add_counterions"])

    def test_selected_charge_model_is_am1bcc(self) -> None:
        self.assertIn("AM1-BCC", self.config["solute"]["charge_model"])

    def test_configured_replicates_have_unique_ids_and_velocity_seeds(self) -> None:
        replicates = self.config["production"]["replicates"]
        self.assertGreaterEqual(len(replicates), 1)
        self.assertEqual(len({item["id"] for item in replicates}), len(replicates))
        self.assertEqual(len({item["velocity_seed"] for item in replicates}), len(replicates))
        self.assertTrue(
            {item["starting_conformer"] for item in replicates}
            <= {"extended", "intermediate", "folded"}
        )

    def test_production_length_and_output_interval(self) -> None:
        """The frozen 2 fs schedule must represent 10 ns with 2 ps frames."""
        prod = parse_mdp(PROJECT_ROOT / "mdp" / "prod.mdp")
        self.assertEqual(float(prod["dt"]), 0.002)
        self.assertEqual(int(prod["nsteps"]), 5_000_000)
        self.assertEqual(float(prod["dt"]) * int(prod["nsteps"]) / 1000, 10.0)
        self.assertEqual(int(prod["nstxout-compressed"]), 1000)
        self.assertEqual(prod["pcoupl"].lower(), "parrinello-rahman")

    def test_nvt_and_npt_lengths(self) -> None:
        nvt = parse_mdp(PROJECT_ROOT / "mdp" / "nvt.mdp")
        npt = parse_mdp(PROJECT_ROOT / "mdp" / "npt.mdp")
        self.assertEqual(int(nvt["nsteps"]), 500_000)
        self.assertEqual(int(npt["nsteps"]), 2_500_000)
        self.assertEqual(npt["pcoupl"].lower(), "c-rescale")

    def test_energy_minimization_pair_list_covers_cutoffs(self) -> None:
        em = parse_mdp(PROJECT_ROOT / "mdp" / "em.mdp")
        self.assertGreaterEqual(float(em["rlist"]), float(em["rcoulomb"]))
        self.assertGreaterEqual(float(em["rlist"]), float(em["rvdw"]))
        self.assertEqual(em["define"], "-DFLEXIBLE")
        self.assertEqual(em["constraints"].lower(), "none")

    def test_common_nonbonded_settings_are_identical(self) -> None:
        keys = {
            "cutoff-scheme",
            "vdwtype",
            "vdw-modifier",
            "rvdw",
            "dispcorr",
            "coulombtype",
            "rcoulomb",
            "fourierspacing",
            "pme-order",
            "ewald-rtol",
        }
        parsed = [parse_mdp(PROJECT_ROOT / "mdp" / name) for name in ("em.mdp", "nvt.mdp", "npt.mdp", "prod.mdp")]
        reference = {key: parsed[0][key] for key in keys}
        for values in parsed[1:]:
            self.assertEqual({key: values[key] for key in keys}, reference)

    def test_site_cutoffs_are_not_preset(self) -> None:
        self.assertTrue(all(value is None for value in self.config["analysis"]["site_cutoffs_nm"].values()))

    def test_only_one_delivered_workflow_entry_exists(self) -> None:
        """The production workflow has one Python entry and no shell runner."""
        script_names = {
            path.name for path in (PROJECT_ROOT / "scripts").glob("run_production.*")
        }
        self.assertEqual(script_names, {"run_production.py"})
        script = (PROJECT_ROOT / "scripts" / "run_production.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ACCEPTED.json", script)
        self.assertIn("topology_sha256", script)
        self.assertIn('"-cpt"', script)
        self.assertNotIn("H:\\", script)
        self.assertNotIn("C:\\", script)

    def test_python_entrypoint_validates_frozen_protocol(self) -> None:
        """The Python entry accepts the frozen inputs and CPU run arguments."""
        config, arguments, checkpoint_minutes = validate_protocol(PROJECT_ROOT)
        self.assertEqual(config["project_id"], "zwitterion_single_molecule_hydration")
        self.assertEqual(arguments, ["-pin", "auto"])
        self.assertEqual(checkpoint_minutes, 10.0)

    def test_python_entrypoint_resolves_an_explicit_executable(self) -> None:
        """An explicit executable path is resolved without a platform shell."""
        self.assertEqual(Path(resolve_gmx(sys.executable)), Path(sys.executable).resolve())

    def test_python_entrypoint_orchestrates_all_production_stages(self) -> None:
        """One new replicate stages inputs and schedules the complete protocol."""
        config, arguments, checkpoint_minutes = validate_protocol(PROJECT_ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            run_root = Path(temporary)
            with patch("scripts.run_production.run_gmx") as mocked_gmx, patch(
                "scripts.run_production.run_mdrun"
            ) as mocked_mdrun:
                run_replicate(
                    sys.executable,
                    PROJECT_ROOT,
                    run_root,
                    config,
                    config["production"]["replicates"][0],
                    8,
                    arguments,
                    checkpoint_minutes,
                )
            self.assertTrue((run_root / "run_001" / "input_manifest.json").is_file())
            self.assertEqual(mocked_gmx.call_count, 6)
            self.assertEqual(mocked_mdrun.call_count, 4)

    def test_scientific_config_contains_no_machine_paths(self) -> None:
        """Runtime paths must be supplied by the caller, not frozen as science."""
        self.assertNotIn("paths", self.config)

    def test_topology_template_omits_zero_water_entry(self) -> None:
        template = (PROJECT_ROOT / "topology" / "system.top.template").read_text(encoding="utf-8")
        self.assertNotIn("SOL     0", template)
        self.assertIn("ZIL     1", template)


if __name__ == "__main__":
    unittest.main()
