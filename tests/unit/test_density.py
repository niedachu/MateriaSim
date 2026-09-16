"""Known-answer density statistics and sealed-energy analysis dispatch contracts."""

import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from materiasim.analysis.density import density_statistics, read_density_frames, validate_density
from materiasim.analysis.registry import get_analyzer, validate_requests
from materiasim.research.compare import verified_report
from materiasim.research.semantics import observables_check
from materiasim.storage import read_json, sha256, write_json
from materiasim.workflows.analysis import analyze


class DensityTests(unittest.TestCase):
    """Use visibly synthetic energy values, not scientific evidence for an actual material."""

    def setUp(self):
        """Create independent fixtures and an explicit 10–13 ps analysis window."""
        temporary = tempfile.TemporaryDirectory(prefix="materiasim-density-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.config = dict(gromacs_command="gmx", begin_ps=10, end_ps=13)
        self.xvg = self.root / "synthetic.xvg"
        self.header = '@ xaxis label "Time (ps)"\n@ yaxis label "(nm^3), (kg/m^3)"\n'
        self.text = (self.header + '@ s0 legend "Volume"\n@ s1 legend "Density"\n'
                     '10 1 1000\n11 2 500\n12 4 250\n13 5 200\n')
        self.xvg.write_text(self.text)

    def test_known_means_units_and_estimator(self):
        """Average instantaneous density, not inverse mean volume; SD is sample spread."""
        rows = read_density_frames(self.xvg, self.config)
        report = density_statistics(rows)
        self.assertEqual(report["mean_density_kg_m3"], 487.5)
        self.assertEqual(report["mean_volume_nm3"], 3)
        self.assertNotEqual(report["mean_density_kg_m3"], 1000 / 3)
        self.assertAlmostEqual(report["frame_sd_volume_nm3"], math.sqrt(10 / 3))

    def test_series_order_is_named_not_positional(self):
        """Native tool selection order may differ, without changing physical columns."""
        self.xvg.write_text(self.header.replace('(nm^3), (kg/m^3)', '(kg/m^3), (nm^3)')
                            + '@ s0 legend "Density"\n@ s1 legend "Volume"\n10 1000 1\n13 500 2\n')
        self.assertEqual(read_density_frames(self.xvg, self.config), [(10, 1000, 1), (13, 500, 2)])

    def test_rejects_invalid_series(self):
        """Missing/duplicate terms, nonfinite/negative data and wrong dimensions fail."""
        changes = [("Density", "Temperature"), ('@ s1', '@ s0'), ('11 2 500', '11 2 nan'),
                   ('11 2 500', '11 0 500'), ('11 2 500', '11 2 -1'),
                   ('11 2 500', '11 2 500 7'), ('11 2 500', '11 2')]
        for old, new in changes:
            with self.subTest(change=(old, new)), self.assertRaises(ValueError):
                self.xvg.write_text(self.text.replace(old, new))
                read_density_frames(self.xvg, self.config)

    def test_rejects_time_gaps_duplicates_and_truncation(self):
        """Arithmetic frame averaging cannot silently accept missing windows or irregular times."""
        for old, new in [('11 2', '10 2'), ('11 2', '9 2'), ('11 2', '11.5 2'),
                         ('13 5 200\n', ''), ('10 1 1000\n', '')]:
            with self.subTest(change=(old, new)), self.assertRaises(ValueError):
                self.xvg.write_text(self.text.replace(old, new))
                read_density_frames(self.xvg, self.config)

    def test_too_few_frames(self):
        """A single saved frame cannot define the declared window or sample spread."""
        self.xvg.write_text(self.header + '@ s0 legend "Volume"\n@ s1 legend "Density"\n10 1 1000\n')
        with self.assertRaisesRegex(ValueError, "At least two"):
            read_density_frames(self.xvg, self.config)

    def test_invalid_config(self):
        """No implicit executable, default equilibration, invalid times or unknown fields."""
        for config in ({}, dict(self.config, begin_ps=True), dict(self.config, end_ps=10),
                       dict(self.config, end_ps=float("inf")), dict(self.config, gromacs_command=""),
                       dict(self.config, guess_mass=True)):
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_density(config)

    def test_rejects_missing_or_wrong_units(self):
        """An energy label alone must not silently bless other time or density units."""
        for old, new in [(self.header, ""), ("Time (ps)", "Time (ns)"),
                         ("kg/m^3", "g/cm^3"), ("nm^3", "A^3")]:
            with self.subTest(change=(old, new)), self.assertRaisesRegex(ValueError, "axes"):
                self.xvg.write_text(self.text.replace(old, new))
                read_density_frames(self.xvg, self.config)

    def test_registration_and_observables(self):
        """Density is a real request and research metric, not a new standalone runner."""
        request = dict(id="density", kind="mass_density", stage_id="sample", config=self.config)
        validate_requests([request], [dict(id="sample", type="dynamics")])
        self.assertEqual(get_analyzer("mass_density").inputs, (("energy", "edr"),))
        observables_check([dict(request_id="density", method="mass_density",
                               metric="mean_density_kg_m3", unit="kg/m^3")])
        with self.assertRaises(ValueError):
            observables_check([dict(request_id="density", method="mass_density",
                                   metric="mean_density_kg_m3", unit="g/cm^3")])

    def _fixture(self):
        """Return a minimal sealed v3 source; no fake molecular mapping is needed for EDR."""
        source = self.root / "run"
        request = dict(id="density", kind="mass_density", stage_id="sample", config=self.config)
        spec = dict(schema_version=3, purpose="engineering_smoke", analysis_requests=[request],
                    protocol=dict(stages=[dict(id="sample", type="dynamics")]))
        manifest = dict(run_id="synthetic", spec_hash="synthetic-spec")
        write_json(source / "status.json", dict(status="completed"))
        write_json(source / "manifest.json", manifest)
        path = "stages/sample/md.edr"
        write_json(source / path, dict(synthetic=True))
        digest = sha256(source / path)
        write_json(source / "stages/sample/stage.json", dict(status="completed", outputs={path: digest},
                   artifacts=dict(energy=dict(path=path, format="edr", sha256=digest))))
        executable = self.root / "fake-executable"
        executable.write_text("not executable; native tool is mocked in this unit test")
        self.engine = dict(executable=str(executable), sha256=sha256(executable), version="synthetic")
        return source, request, spec, manifest

    def _command(self, engine, arguments, cwd, record, inputs, **kwargs):
        """Replace only external extraction; assert private input and bounded named selection."""
        self.assertEqual(kwargs["seconds"], 60)
        self.assertEqual(kwargs["stdin"], "Density\nVolume\n0\n")
        self.assertEqual(Path(arguments[2]).parent, cwd / "inputs")
        self.assertIn("-dp", arguments)
        Path(arguments[4]).write_text(self.text)
        write_json(record / "command.json", dict(synthetic=True))
        (record / "stdout.log").write_text("synthetic")
        (record / "stderr.log").write_text("synthetic")
        return dict(interrupted=False)

    def test_dispatch_private_inputs_and_verified_result(self):
        """Real dispatch, sealing and research verification work for an analyzer without mapping."""
        source, request, spec, manifest = self._fixture()
        before = {p.relative_to(source): sha256(p) for p in source.rglob("*") if p.is_file()}
        with patch("materiasim.workflows.analysis.verify_run", return_value=(spec, manifest)), patch(
                "materiasim.analysis.density.engine_info", return_value=self.engine), patch(
                "materiasim.analysis.density.command", side_effect=self._command):
            outputs = analyze(source, self.root / "analyses")
        folder = Path(outputs[0])
        report = verified_report(folder, source, spec, manifest)
        self.assertNotIn("mapping_sha256", report)
        self.assertEqual(report["mean_density_kg_m3"], 487.5)
        self.assertEqual(report["result_contract"]["method"], "mass_density")
        self.assertIsNone(report["confidence_interval"])
        self.assertIsNone(report["standard_error"])
        self.assertEqual(report["scientific_quality"], "not_assessed")
        self.assertEqual(before, {p.relative_to(source): sha256(p) for p in source.rglob("*") if p.is_file()})
        (folder / "density_volume.xvg").write_text("tampered")
        with self.assertRaises(ValueError):
            verified_report(folder, source, spec, manifest)

    def test_missing_energy_role_fails_before_output(self):
        """Do not infer missing density or silently substitute GRO masses."""
        source, request, spec, manifest = self._fixture()
        write_json(source / "stages/sample/stage.json", dict(status="completed", artifacts={}))
        with patch("materiasim.workflows.analysis.verify_run", return_value=(spec, manifest)):
            with self.assertRaisesRegex(ValueError, "missing role"):
                analyze(source, self.root / "analyses")
        self.assertFalse((self.root / "analyses").exists())

    def test_interrupted_extraction_preserves_failed_analysis(self):
        """A nominally zero-exit interrupted command cannot publish partial statistics."""
        source, request, spec, manifest = self._fixture()
        with patch("materiasim.workflows.analysis.verify_run", return_value=(spec, manifest)), patch(
                "materiasim.analysis.density.engine_info", return_value=self.engine), patch(
                "materiasim.analysis.density.command", return_value=dict(interrupted=True)):
            with self.assertRaisesRegex(ValueError, "interrupted"):
                analyze(source, self.root / "analyses")
        folders = list((self.root / "analyses").iterdir())
        self.assertEqual(len(folders), 1)
        self.assertEqual(read_json(folders[0] / "status.json")["status"], "failed")
        self.assertFalse((folders[0] / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
