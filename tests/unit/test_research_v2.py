"""Research v2 admission and method-owned observations, using unchanged catalog models."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from materiasim.analysis.registry import get_analyzer
from materiasim.research.plan import load_plan, plan
from materiasim.research.schema import expand, projection
from materiasim.research.semantics import apply_repeat, evaluate_rules, seed_values
from materiasim.specs.execution import cpu_profile
from materiasim.storage import content_hash, inventory, read_json, write_json
from materiasim.workflows.migration import load_executable, portable_document
from materiasim.workflows.validation import validate_resolved

ROOT = Path(__file__).resolve().parents[2]


def research_fixture(root, analyze=True):
    """Write isolated two-case/two-repeat input variants with identical scientific models and protocols."""
    records = [load_executable(ROOT / "examples" / (name + ".json"))
               for name in ("cat_ani_smoke", "packed_ions_water")]
    requests = records[0][0]["analysis_requests"] + records[1][0]["analysis_requests"] if analyze else []
    cases = []
    for index, (spec, sources, _, _) in enumerate(records):
        spec["execution_profile"] = cpu_profile()
        spec["analysis_requests"] = deepcopy(requests)
        validate_resolved(spec, sources)
        target = root / "source" / f"case-{index}.json"
        write_json(target, portable_document(spec, sources))
        repeats = [dict(id=f"r{n}", seeds={key: 10001 + index * 100 + n * 10 + j
                                         for j, key in enumerate(seed_values(spec))}) for n in (1, 2)]
        cases.append(dict(id=f"case-{index}", experiment=target.name, repeats=repeats))
    definition = dict(schema_version=2, id="framework_research", revision=1,
        question="Can both existing builders and both methods share the same bounded research core?",
        hypothesis="Every declared task retains evidence; no scientific claim.", purpose="engineering_smoke",
        baseline_case="case-0", varied_factors=["scenario", "component_counts"],
        controlled_factors=["Identical CAT/ANI models, protocol, analysis selections and units"],
        observables=[dict(request_id=r["id"], method=r["kind"], metric=metric, unit=unit)
                     for r in requests for metric, unit in get_analyzer(r["kind"]).metrics],
        decision_rules=dict(description="Engineering evidence only", checks=[dict(id="complete", kind="all_tasks_completed"),
                             dict(id="analysis", kind="analysis_valid")]),
        cases=cases, limits=dict(max_tasks=4, concurrency=1, total_seconds=1800, storage_bytes=1073741824),
        sources=["Existing catalog CAT/ANI engineering examples; no new scientific model"])
    source = root / "source/research.json"
    write_json(source, definition)
    return source, definition


class ResearchV2Tests(unittest.TestCase):
    """Validate general research without substituting fake successful MD evidence."""

    def setUp(self):
        """Create temporary derived configurations; original assets stay read-only."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source, self.definition = research_fixture(self.root)

    def reject(self):
        """Reject an edited research declaration before creating a plan or launching tools."""
        write_json(self.source, self.definition)
        with self.assertRaises(ValueError):
            expand(self.source)

    def test_mixed_builders_and_methods(self):
        """Prebuilt repeats omit packing seeds; both methods are represented in all four tasks."""
        before = inventory(self.root, ["source"])
        with patch("subprocess.Popen", side_effect=AssertionError("engine launch")):
            expanded = expand(self.source)
        self.assertEqual(expanded["schema_version"], 3)
        self.assertEqual(len(expanded["tasks"]), 4)
        self.assertEqual(set(expanded["tasks"][0]["repeat"]["seeds"]), {"velocity_nvt"})
        self.assertEqual(set(expanded["tasks"][2]["repeat"]["seeds"]), {"packing", "velocity_nvt"})
        self.assertEqual(len(expanded["tasks"][0]["spec"]["analysis_requests"]), 2)
        self.assertEqual(inventory(self.root, ["source"]), before)

    def test_frozen_plan_revalidates_new_semantics(self):
        """Portable v3 frozen plans retain Research v2, original documents and exactly assigned slots."""
        target = self.root / "plan"
        plan(self.source, target)
        value = load_plan(target)
        self.assertEqual(value["research"]["schema_version"], 2)
        self.assertTrue((target / "tasks/task-000/origin/derivation.json").is_file())

    def test_prebuilt_packing_and_missing_velocity_seeds_rejected(self):
        """A nonexistent or missing slot cannot be silently ignored or randomly generated."""
        self.definition["cases"][0]["repeats"][0]["seeds"]["packing"] = 3
        self.reject()
        del self.definition["cases"][0]["repeats"][0]["seeds"]["packing"]
        self.definition["cases"][0]["repeats"][0]["seeds"] = {}
        self.reject()

    def test_duplicate_assignment_and_unknown_override_rejected(self):
        """Duplicate seed maps and arbitrary repeat overrides remain forbidden."""
        repeats = self.definition["cases"][0]["repeats"]
        repeats[1]["seeds"] = deepcopy(repeats[0]["seeds"])
        self.reject()
        repeats[1]["seeds"]["velocity_nvt"] += 1
        repeats[0]["temperature"] = 300
        self.reject()

    def test_no_analysis_is_explicit(self):
        """Execution-only research needs neither dummy observables nor analysis outputs."""
        source, _ = research_fixture(self.root, analyze=False)
        expanded = expand(source)
        self.assertEqual(expanded["research"]["observables"], [])
        self.assertTrue(all(not t["spec"]["analysis_requests"] for t in expanded["tasks"]))

    def test_undeclared_method_unit_and_observation_rejected(self):
        """Methods own metric units; a missing request cannot be silently dropped."""
        self.definition["observables"][0]["unit"] = "kJ/mol"
        self.reject()
        self.definition["observables"] = []
        self.reject()

    def test_undeclared_scenario_rejected(self):
        """Different geometry/build semantics require explicit declaration."""
        self.definition["varied_factors"] = ["component_counts"]
        self.reject()

    def test_method_observation_values_and_quality(self):
        """Known numeric method summaries stay separated; missing evidence is not a passing rule."""
        water = get_analyzer("hydration_contacts").observations(dict(summary=dict(union=dict(mean=4))))
        pairs = get_analyzer("component_contacts").observations(dict(mean_unique_molecule_pairs=2, normalization="raw"))
        self.assertNotEqual(water["metrics"][0]["unit"], pairs["metrics"][0]["unit"])
        rule = dict(description="Engineering range", checks=[dict(id="range", kind="metric_range",
                    request_id="a", metric="mean_union_water_contacts", unit="water_molecules", minimum=0, maximum=3)])
        rows = [dict(task_id="a", status="completed", observations=[dict(request_id="a", report_sha256="fixture", **water["metrics"][0])])]
        self.assertEqual(evaluate_rules(rule, rows)["checks"][0]["status"], "fail")
        rows[0]["observations"] = []
        self.assertEqual(evaluate_rules(rule, rows)["checks"][0]["status"], "not_assessed")

    def test_range_rules_validate_metric_and_unit(self):
        """A structured check cannot refer to an undeclared scientific metric."""
        self.definition["decision_rules"]["checks"].append(dict(id="bad", kind="metric_range", request_id="x",
            metric="free_energy", unit="kJ/mol", minimum=0, maximum=1))
        self.reject()

    def test_profile_resources_do_not_change_physical_comparison(self):
        """Different explicit thread budgets do not masquerade as a changed model or protocol."""
        tasks = expand(self.source)["tasks"]
        left, right = deepcopy(tasks[0]["spec"]), deepcopy(tasks[0]["spec"])
        right["execution_profile"]["threads"] = 1
        self.assertEqual(projection(left, [], 2), projection(right, [], 2))
        right["protocol"]["stages"][1]["steps"] = 900
        self.assertNotEqual(projection(left, [], 2), projection(right, [], 2))


if __name__ == "__main__":
    unittest.main()
