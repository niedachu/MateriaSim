"""Explicit local review attestations; engineering success never grants scientific approval."""

from copy import deepcopy
from datetime import datetime

from materiasim.specs.schema import fields, integer
from materiasim.storage import content_hash, read_json, sha256


def target_hash(spec):
    """Identify the reviewed physical design, excluding repeat seeds, paths and resource allocations."""
    target = deepcopy({k: v for k, v in spec.items() if k not in
                       ("id", "purpose_policy", "execution_profile", "analysis_requests")})
    for stage in target["protocol"]["stages"]:
        if stage["velocities"] == "generate":
            stage["seed"] = "declared_repeat"
    config = target["scenario"]["builder"]["config"]
    if "seed" in config:
        config["seed"] = "declared_repeat"
    return content_hash(target)


def text(value, label):
    """Require an explicit nonempty human declaration, without treating it as authenticated identity."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: explicit text required")


def validate_policy(spec, sources):
    """Require hashed review evidence for non-smoke work, retaining all parameter hard checks."""
    if spec["purpose"] == "engineering_smoke":
        return
    from materiasim.specs.v3 import digest
    policy = spec["purpose_policy"]
    fields(policy, ("contract_version", "intent", "reviewer", "reviewed_utc", "target_hash",
                    "environment", "evidence", "files"), "purpose_policy")
    integer(policy["contract_version"], 1, 1, "purpose_policy version")
    for key in ("intent", "reviewer", "reviewed_utc"):
        text(policy[key], key)
    date = datetime.fromisoformat(policy["reviewed_utc"])
    if date.utcoffset() is None:
        raise ValueError("Review timestamp requires an explicit timezone")
    if policy["target_hash"] != target_hash(spec):
        raise ValueError("Purpose review does not cover this physical design")
    if spec["execution_profile"]["contract_version"] != 3:
        raise ValueError("Non-smoke work requires explicit execution profile v3")
    if output_estimate(spec) > spec["execution_profile"]["storage_bytes"]:
        raise ValueError("Reviewed protocol output estimate exceeds storage allowance")
    environment = policy["environment"]
    fields(environment, ("platform", "engine_version", "engine_sha256"), "review environment")
    if environment["platform"] not in ("darwin", "linux"):
        raise ValueError("Review must identify the target macOS/Linux environment")
    text(environment["engine_version"], "engine_version")
    digest(environment["engine_sha256"], "engine_sha256")
    roles = {"parameter_review", "protocol_review", "validation_design"}
    if spec["purpose"] == "production":
        roles = {"parameter_review", "protocol_review", "applicability_validation"}
        if spec["interaction_bundle"]["validation_scope"] != "reviewed":
            raise ValueError("Production rejects engineering_only interaction bundles")
        if any(c["model"]["provenance"]["status"] != "declared" or c["model"]["resolution"] == "unspecified"
               or c["role"] == "unspecified" for c in spec["components"]):
            raise ValueError("Production requires declared model provenance, resolution and roles")
    fields(policy["evidence"], roles, "purpose evidence roles")
    assets = {item["name"]: item for item in policy["files"]}
    if set(policy["evidence"].values()) != set(assets) or len(assets) != len(roles):
        raise ValueError("Purpose evidence requires one distinct declared JSON artifact per role")
    for role, name in policy["evidence"].items():
        if assets[name]["format"] != "json" or sha256(sources[name]) != assets[name]["sha256"]:
            raise ValueError("Purpose evidence asset changed")
        record = read_json(sources[name])
        fields(record, ("contract_version", "kind", "decision", "target_hash", "reviewer", "basis", "limitations"), "review evidence")
        integer(record["contract_version"], 1, 1, "evidence version")
        if (record["kind"] != role or record["decision"] != "accepted" or
                record["target_hash"] != policy["target_hash"] or record["reviewer"] != policy["reviewer"]):
            raise ValueError("Purpose evidence does not approve the declared review scope")
        for key in ("basis", "limitations"):
            text(record[key], key)


def validate_environment(spec, engine):
    """Reject execution/build on a native engine outside the explicitly reviewed environment."""
    if spec["purpose"] != "engineering_smoke":
        expected = spec["purpose_policy"]["environment"]
        if expected != dict(platform=engine["platform"], engine_version=engine["version"], engine_sha256=engine["sha256"]):
            raise ValueError("Native environment differs from purpose approval")


def select_tool(profile, name, supplied=None):
    """Resolve v3 frozen tool locators; old profiles retain actual CLI-selected tool behavior."""
    if profile["contract_version"] == 3:
        selected = profile["tools"][name]
        if supplied is not None and supplied != selected:
            raise ValueError("CLI tool differs from frozen execution profile")
        return selected
    return supplied if supplied is not None else name


def output_estimate(spec, atom_count=20000):
    """Estimate bytes at the retained atom ceiling, including append/analysis copies; not a hard bound."""
    estimated = 64 * 1024 * 1024
    for stage in spec["protocol"]["stages"]:
        sampling = stage["sampling"]
        estimated += (stage["steps"] // sampling["trajectory_steps"] + 1) * (atom_count * 12 + 4096)
        estimated += (stage["steps"] // sampling["energy_steps"] + 1) * 65536
        estimated += (stage["steps"] // sampling["log_steps"] + 1) * 8192
    return estimated * (2 + spec["execution_profile"]["max_attempts"] + len(spec["analysis_requests"]))
