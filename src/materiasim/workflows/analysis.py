"""Analysis request dispatch and independent immutable-input AnalysisRun generations."""

import shutil
import uuid
from pathlib import Path

from materiasim.specs.analysis import analysis_requests
from materiasim.storage import source_root, content_hash, read_json, sha256, utc_now, write_json
from materiasim.analysis.hydration import hydration_contacts
from materiasim.analysis.component_contacts import component_contacts
from materiasim.runtime.records import stage_artifact, stage_ids
from materiasim.runtime.state import source_identity, verify_run


def selected_requests(spec, request):
    """Resolve explicit or configured tasks; only historical v1 supplies its old hydration default."""
    if request is not None:
        requests = [request]
    elif spec["schema_version"] == 1:
        requests = [dict(id="legacy_hydration", kind="hydration_contacts", stage_id="prod", config=spec["analysis"])]
    else:
        requests = spec["analysis_requests"]
    stages = (spec["protocol"]["stages"] if spec["schema_version"] == 2 else
              [dict(id=name, type="minimization" if name == "em" else "dynamics") for name in stage_ids(spec)])
    return analysis_requests(requests, stages)


def analyze_one(root, output_root, spec, manifest, request):
    """Freeze analysis inputs externally and dispatch the requested contact algorithm with its own status."""
    topology = stage_artifact(root, spec, request["stage_id"], "coordinates")
    trajectory = stage_artifact(root, spec, request["stage_id"], "trajectory")
    mapping_path = root / "build/atom_mapping.json"
    output = output_root / (manifest["run_id"] + "--" + request["id"] + "--" + uuid.uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    identity = dict(run_id=manifest["run_id"], spec_hash=manifest["spec_hash"], request=request,
                    request_hash=content_hash(request), source_run=str(root), source_schema=spec["schema_version"],
                    source_manifest_sha256=sha256(root / "manifest.json"), implementation=source_identity(),
                    created_utc=utc_now())
    write_json(output / "request.json", identity)
    write_json(output / "status.json", dict(status="running"))
    try:
        inputs = output / "inputs"
        inputs.mkdir()
        # MDAnalysis creates XTC offset caches alongside a trajectory; only our private
        # snapshot may be opened, so even legacy Run cache/lock bytes remain unchanged.
        frozen = {}
        for source, name in ((topology, "coordinates.gro"), (trajectory, "trajectory.xtc"), (mapping_path, "mapping.json")):
            digest = sha256(source)
            destination = inputs / name
            shutil.copyfile(source, destination)
            if sha256(destination) != digest or sha256(source) != digest:
                raise ValueError("Analysis source changed while copying")
            frozen[name] = dict(source=source.relative_to(root).as_posix(), sha256=digest)
        verify_run(root)
        write_json(output / "inputs.json", frozen)
        algorithm = {"hydration_contacts": hydration_contacts, "component_contacts": component_contacts}[request["kind"]]
        report = algorithm(inputs / "coordinates.gro", inputs / "trajectory.xtc",
                           read_json(inputs / "mapping.json"), request["config"], output, identity)
        report.update(stage_id=request["stage_id"], analysis_request=request,
                      request_hash=identity["request_hash"], source_schema=spec["schema_version"],
                      mapping_sha256=frozen["mapping.json"]["sha256"])
        write_json(output / "report.json", report)
        write_json(output / "status.json", dict(status="completed", report_sha256=sha256(output / "report.json")))
    except Exception as error:
        write_json(output / "status.json", dict(status="failed", error=str(error)))
        raise
    return str(output)


def analyze(run, output_root, request=None):
    """Analyze completed sealed stages into an explicit external root; [] creates no output."""
    root = Path(run).resolve()
    spec, manifest = verify_run(root)
    if read_json(root / "status.json")["status"] != "completed":
        raise ValueError("Analysis requires a completed Run")
    requests = selected_requests(spec, request)
    output_root = Path(output_root).resolve()
    protected_source = source_root()
    for protected in (root, protected_source):
        if output_root == protected or protected in output_root.parents:
            raise ValueError("Analysis output must be outside the Run and framework source")
    return [analyze_one(root, output_root, spec, manifest, item) for item in requests]
