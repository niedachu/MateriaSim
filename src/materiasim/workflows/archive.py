"""Portable read-only evidence bundles; export copies never re-open or relocate active computation."""

from pathlib import Path

from materiasim.runtime.capacity import copy_budget, copy_tree, files_under, preflight
from materiasim.runtime.control import inspect_control
from materiasim.runtime.journal import validate_journal
from materiasim.runtime.state import verify_run
from materiasim.storage import contained, content_hash, read_json, sha256, verify_hashes, write_json
from materiasim.specs.schema import fields, integer
from materiasim.research.plan import external_output


def export_archive(run, output, max_bytes):
    """Copy a completed Run and its closed control/analysis evidence to an explicit new bounded bundle."""
    run = Path(run).resolve()
    integer(max_bytes, 1048576, 1099511627776, "archive max_bytes")
    spec, manifest = verify_run(run)
    if read_json(run / "status.json")["status"] != "completed":
        raise ValueError("Only completed Runs can be exported as portable read-only archives")
    entries = [dict(role="run", original=str(run), path="runs/" + run.name)]
    if "operation_control" in manifest:
        control, ledger = inspect_control(run, spec["execution_profile"], manifest["spec_hash"])
        entries.append(dict(role="control", original=str(control), path="runs/.materiasim-operations/" + run.name))
        for index, path in enumerate(ledger["outputs"]):
            if not Path(path).is_dir():
                raise ValueError("Registered analysis output missing; archive would be incomplete")
            entries.append(dict(role="analysis", original=path, path=f"analyses/{index:04d}"))
    output = external_output(output, [Path(e["original"]) for e in entries])
    if output.exists():
        raise FileExistsError(output)
    before = {e["path"]: tree_hashes(Path(e["original"])) for e in entries}
    with copy_budget([output], max_bytes, 64 * 1024 * 1024):
        preflight([e["original"] for e in entries], output)
        output.mkdir(parents=True, exist_ok=False)
        for entry in entries:
            target = contained(output, entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_tree(entry["original"], target)
        if before != {e["path"]: tree_hashes(Path(e["original"])) for e in entries}:
            raise ValueError("Source evidence changed during archive export")
        hashes = tree_hashes(output)
        record = dict(contract_version=1, mode="read_only", entries=entries, hashes=hashes, max_bytes=max_bytes)
        record["archive_hash"] = content_hash(record)
        write_json(output / "archive.json", record)
        preflight([], output)
    return verify_archive(output)


def tree_hashes(root):
    """Inventory all regular bytes below one existing tree using contained relative paths."""
    root = Path(root)
    return {str(p.relative_to(root)): sha256(p) for p in files_under(root)}


def validate_entries(root, entries):
    """Require unique, nonoverlapping archive trees and lexical original-path provenance only."""
    if not isinstance(entries, list) or not entries:
        raise ValueError("Archive entries must be a nonempty list")
    paths, originals = [], []
    for entry in entries:
        fields(entry, ("role", "original", "path"), "archive entry")
        if entry["role"] not in ("run", "control", "analysis"):
            raise ValueError("Unknown archive entry role")
        if not isinstance(entry["original"], str) or not Path(entry["original"]).is_absolute():
            raise ValueError("Archive original must be absolute path provenance")
        path = contained(root, entry["path"])
        if not path.is_dir() or any(path == p or path in p.parents or p in path.parents for p in paths):
            raise ValueError("Archive entry trees overlap or are missing")
        paths.append(path)
        originals.append(entry["original"])
    if len(originals) != len(set(originals)):
        raise ValueError("Duplicate archive original")


def verify_analyses(root, entries, run, spec, manifest):
    """Cross-check every archived completed analysis, including explicit independent requests."""
    from materiasim.analysis.locations import generations
    from materiasim.research.compare import verified_report
    for entry in entries:
        if entry["role"] != "analysis":
            continue
        folders = generations(contained(root, entry["path"]))
        if not folders:
            raise ValueError("Archive analysis namespace is empty")
        for folder in folders:
            request = read_json(folder / "request.json")["request"]
            verified_report(folder, run, spec, manifest, independent_request=request)


def verify_archive(root):
    """Verify an archive using only its local copies, without resolving original machine paths."""
    root = Path(root).resolve()
    record = read_json(root / "archive.json")
    fields(record, ("contract_version", "mode", "entries", "hashes", "max_bytes", "archive_hash"), "archive")
    integer(record["contract_version"], 1, 1, "archive version")
    integer(record["max_bytes"], 1048576, 1099511627776, "archive max_bytes")
    if record["mode"] != "read_only" or content_hash({k: v for k, v in record.items() if k != "archive_hash"}) != record["archive_hash"]:
        raise ValueError("Archive manifest identity changed")
    verify_hashes(root, record["hashes"])
    actual = tree_hashes(root)
    actual.pop("archive.json")
    if actual != record["hashes"]:
        raise ValueError("Archive file inventory differs")
    if sum(p.stat().st_size for p in files_under(root)) > record["max_bytes"]:
        raise ValueError("Archive exceeds declared storage allowance")
    validate_entries(root, record["entries"])
    runs = [entry for entry in record["entries"] if entry["role"] == "run"]
    controls = [entry for entry in record["entries"] if entry["role"] == "control"]
    if len(runs) != 1 or len(controls) > 1:
        raise ValueError("Archive requires exactly one Run and at most one control journal")
    run = contained(root, runs[0]["path"])
    spec, manifest = verify_run(run)
    if read_json(run / "status.json")["status"] != "completed":
        raise ValueError("Archive Run is not completed")
    if controls:
        entry = controls[0]
        ledger = validate_journal(contained(root, entry["path"]), run, spec["execution_profile"],
                                  manifest["spec_hash"], recorded_root=entry["original"])
        if [e["original"] for e in record["entries"] if e["role"] == "analysis"] != ledger["outputs"]:
            raise ValueError("Archive omitted registered analysis evidence")
    elif "operation_control" in manifest:
        raise ValueError("Archive omitted its bound control journal")
    verify_analyses(root, record["entries"], run, spec, manifest)
    return dict(archive_dir=str(root), archive_hash=record["archive_hash"], integrity="verified",
                mode="read_only", run_id=manifest["run_id"], scientific_quality="not_assessed")
