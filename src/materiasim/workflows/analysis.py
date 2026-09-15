"""Analysis request dispatch and independent immutable-input AnalysisRun generations."""

from materiasim.runtime.capacity import copy_file, preflight
import uuid
from pathlib import Path

from materiasim.analysis.registry import get_analyzer, validate_requests
from materiasim.analysis.contracts import resolve_inputs, result_envelope
from materiasim.storage import source_root, content_hash, read_json, sha256, utc_now, write_json
from materiasim.runtime.records import stage_ids
from materiasim.runtime.state import source_identity, verify_run
from materiasim.runtime.identity import implementation


def selected_requests(spec, request):
    """Resolve explicit or configured tasks; only historical v1 supplies its old hydration default."""
    if request is not None:
        requests = [request]
    elif spec["schema_version"] == 1:
        requests = [dict(id="legacy_hydration", kind="hydration_contacts", stage_id="prod", config=spec["analysis"])]
    else:
        requests = spec["analysis_requests"]
    stages = (spec["protocol"]["stages"] if spec["schema_version"] in (2, 3) else
              [dict(id=name, type="minimization" if name == "em" else "dynamics") for name in stage_ids(spec)])
    return validate_requests(requests, stages)


def analyze_one(root, output_root, spec, manifest, request):
    """Admit input copy bytes, freeze them externally and dispatch the configured analysis."""
    analyzer = get_analyzer(request["kind"])
    artifacts = resolve_inputs(root, spec, request["stage_id"], analyzer)
    output = output_root / (manifest["run_id"] + "--" + request["id"] + "--" + uuid.uuid4().hex)
    preflight([source for source, _ in artifacts.values()], output)
    output.mkdir(parents=True, exist_ok=False)
    identity = dict(run_id=manifest["run_id"], spec_hash=manifest["spec_hash"], request=request,
                    request_hash=content_hash(request), source_run=str(root), source_schema=spec["schema_version"],
                    source_manifest_sha256=sha256(root / "manifest.json"), implementation=source_identity(),
                    created_utc=utc_now())
    identity["analysis_implementation"] = implementation("analysis")
    write_json(output / "request.json", identity)
    write_json(output / "status.json", dict(status="running"))
    try:
        inputs = output / "inputs"
        inputs.mkdir()
        # MDAnalysis creates XTC offset caches alongside a trajectory; only our private
        # snapshot may be opened, so even legacy Run cache/lock bytes remain unchanged.
        frozen, private_inputs = {}, {}
        for role, (source, name) in artifacts.items():
            digest = sha256(source)
            destination = inputs / name
            copy_file(source, destination)
            if sha256(destination) != digest or sha256(source) != digest:
                raise ValueError("Analysis source changed while copying")
            frozen[name] = dict(source=source.relative_to(root).as_posix(), sha256=digest)
            private_inputs[role] = destination
        verify_run(root)
        write_json(output / "inputs.json", frozen)
        report = analyzer.calculate(private_inputs, request["config"], output, identity)
        report["result_contract"] = result_envelope(report, request, identity)
        report.update(purpose=spec["purpose"], stage_id=request["stage_id"], analysis_request=request,
                      request_hash=identity["request_hash"], source_schema=spec["schema_version"],
                      mapping_sha256=frozen["mapping.json"]["sha256"])
        write_json(output / "report.json", report)
        write_json(output / "status.json", dict(status="completed", report_sha256=sha256(output / "report.json")))
    except Exception as error:
        write_json(output / "status.json", dict(status="failed", error=str(error)))
        raise
    return str(output)


def analyze(run, output_root, request=None):
    """Analyze externally while charging v2-profile work to its sibling resource journal, never the MD Run."""
    root = Path(run).resolve()
    spec, _ = verify_run(root)
    if spec.get("execution_profile", {}).get("contract_version") in (2, 3) and selected_requests(spec, request):
        from materiasim.runtime.control import supervise
        from materiasim.research.plan import external_output
        output = external_output(output_root, [root, root.parent / ".materiasim-operations"])
        output = output / ("operation-" + uuid.uuid4().hex)
        return supervise(root, spec, "materiasim.workflows.analysis", "analyze",
                         dict(run=str(root), output_root=str(output), request=request), analysis_output=output)
    return _analyze(run, output_root, request)


def _analyze(run, output_root, request=None, _control=None):
    """Analyze completed sealed stages into an explicit external root; [] creates no output."""
    root = Path(run).resolve()
    spec, manifest = verify_run(root)
    if _control is not None and manifest["spec_hash"] != _control["expected_spec_hash"]:
        raise ValueError("Run changed before supervised analysis")
    if read_json(root / "status.json")["status"] != "completed":
        raise ValueError("Analysis requires a completed Run")
    requests = selected_requests(spec, request)
    output_root = Path(output_root).resolve()
    protected_source = source_root()
    for protected in (root, protected_source):
        if output_root == protected or protected in output_root.parents:
            raise ValueError("Analysis output must be outside the Run and framework source")
    return [analyze_one(root, output_root, spec, manifest, item) for item in requests]


if __name__ == "__main__":
    from materiasim.runtime.control import worker_main
    worker_main(_analyze)
