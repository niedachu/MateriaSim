"""Verified engineering comparison with explicit incomplete rows and no invented inference."""

import uuid
from pathlib import Path

from materiasim.storage import content_hash, read_json, sha256, verify_hashes, write_json
from materiasim.research.plan import external_output, load_plan
from materiasim.runtime.records import stage_artifact
from materiasim.runtime.state import verify_run


def verified_report(folder, root, spec, manifest):
    """Verify report, CSV and frozen analysis sources against the exact sealed Run and request."""
    state = read_json(folder / "status.json")
    if state["status"] != "completed":
        raise ValueError("Analysis is incomplete or failed; no implicit reanalysis")
    if sha256(folder / "report.json") != state["report_sha256"]:
        raise ValueError("Analysis report changed")
    report, identity = read_json(folder / "report.json"), read_json(folder / "request.json")
    request = identity["request"]
    if request not in spec["analysis_requests"] or request["kind"] != "component_contacts":
        raise ValueError("Analysis request differs from frozen research observation")
    expected = dict(run_id=manifest["run_id"], spec_hash=manifest["spec_hash"], request_hash=content_hash(request))
    if any(identity[k] != v or report[k] != v for k, v in expected.items()):
        raise ValueError("Analysis source/request identity mismatch")
    if identity["source_manifest_sha256"] != sha256(root / "manifest.json"):
        raise ValueError("Analysis source manifest changed")
    if (report["analysis_request"] != request or report["selection"] != request["config"]
            or report["stage_id"] != request["stage_id"] or report["kind"] != request["kind"]):
        raise ValueError("Report observation semantics differ from request")
    frozen = read_json(folder / "inputs.json")
    expected_paths = dict(coordinates=stage_artifact(root, spec, request["stage_id"], "coordinates"),
                          trajectory=stage_artifact(root, spec, request["stage_id"], "trajectory"),
                          mapping=root / "build/atom_mapping.json")
    for name, role in (("coordinates.gro", "coordinates"), ("trajectory.xtc", "trajectory"), ("mapping.json", "mapping")):
        digest = sha256(expected_paths[role])
        if frozen[name] != dict(source=expected_paths[role].relative_to(root).as_posix(), sha256=digest):
            raise ValueError("Analysis input differs from sealed stage")
        verify_hashes(folder, {"inputs/" + name: digest})
        report_key = "topology_sha256" if role == "coordinates" else role + "_sha256"
        if report[report_key] != digest:
            raise ValueError("Report input identity differs from snapshot")
    verify_hashes(folder, {"component_contacts.csv": report["csv_sha256"]})
    return dict(report, analysis_dir=str(folder), report_sha256=sha256(folder / "report.json"),
                analysis_implementation=identity["implementation"])


def task_reports(batch, task, record, required=False):
    """Return all verified configured analyses; partial sets are errors, never silently omitted."""
    root = Path(batch) / "runs" / record["run_id"]
    parent = Path(batch) / "analyses" / task["id"]
    folders = sorted(parent.iterdir()) if parent.exists() else []
    if not folders:
        if required or parent.exists():
            raise ValueError("Missing registered analysis evidence")
        return []
    spec, manifest = verify_run(root)
    reports = [verified_report(p, root, spec, manifest) for p in folders]
    if sorted(r["request_hash"] for r in reports) != sorted(content_hash(r) for r in spec["analysis_requests"]):
        raise ValueError("Duplicate or incomplete configured analysis set")
    return reports


def compare(batch, output=None):
    """Summarize every task, checking comparability before aggregate raw contact means."""
    from materiasim.research.batch import validate_batch, task_state
    batch = Path(batch).resolve()
    plan, ledger = validate_batch(batch)
    rows, signatures = [], {}
    for task, record in zip(plan["tasks"], ledger["tasks"]):
        row = dict(task_id=task["id"], case_id=task["case_id"], repeat=task["repeat"],
                   run_id=record["run_id"], spec_hash=task["spec_hash"], observations=[])
        try:
            row["status"] = task_state(batch, task, record)
            if row["status"] == "completed":
                reports = task_reports(batch, task, record, required=True)
                row["composition"] = read_json(batch / "runs" / record["run_id"] / "build/atom_mapping.json")["counts"]
                for report in reports:
                    signature = {key: report[key] for key in ("selection", "normalization", "stage_id",
                                 "frames", "time_range_ps", "equilibration_discard_ps", "versions", "analysis_implementation")}
                    request_id = report["analysis_request"]["id"]
                    if request_id in signatures and signatures[request_id] != signature:
                        raise ValueError("Analysis windows/normalization/implementation are not comparable")
                    signatures[request_id] = signature
                    row["observations"].append(dict(request_id=request_id,
                        mean_unique_molecule_pairs=report["mean_unique_molecule_pairs"],
                        unit="molecule_pairs", analysis_dir=report["analysis_dir"],
                        report_sha256=report["report_sha256"], frames=report["frames"],
                        time_range_ps=report["time_range_ps"]))
        except (ValueError, OSError, KeyError) as error:
            row.update(status="invalid_or_incomplete_evidence", error=str(error), observations=[])
        rows.append(row)
    complete = all(row["status"] == "completed" and row["observations"] for row in rows)
    result = dict(plan_hash=plan["plan_hash"], research_hash=plan["research_hash"],
                  baseline_case=plan["research"]["baseline_case"], varied_factors=plan["research"]["varied_factors"],
                  status="engineering_complete" if complete else "incomplete", tasks=rows,
                  aggregates=[], scientific_quality="not_assessed", confidence_interval=None,
                  independent_samples=None, warning="Raw counts depend on composition; short repeats do not establish equilibrium or binding affinity.")
    if complete:
        for case in plan["research"]["cases"]:
            selected = [r for r in rows if r["case_id"] == case["id"]]
            for request_id in signatures:
                values = [o["mean_unique_molecule_pairs"] for r in selected for o in r["observations"] if o["request_id"] == request_id]
                result["aggregates"].append(dict(case_id=case["id"], request_id=request_id,
                    declared_repeats=len(selected), mean_of_run_means=sum(values) / len(values), unit="molecule_pairs"))
    if output is not None:
        root = external_output(output, [batch]) / ("comparison-" + uuid.uuid4().hex)
        root.mkdir(parents=True, exist_ok=False)
        write_json(root / "report.json", result)
        return dict(comparison_dir=str(root), **result)
    return result
