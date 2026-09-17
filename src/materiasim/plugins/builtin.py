"""Resolve the registries actually consumed by the existing simulation workflows."""

from materiasim.storage import content_hash
from materiasim.runtime.state import source_identity
from materiasim.plugins.graph import order
from materiasim.errors import MateriaSimError, MissingDependency


def catalog():
    """Return descriptors derived from real registrations, not promises of scientific validity."""
    from materiasim.engines.registry import ENGINES
    from materiasim.builders.registry import BUILDERS
    from materiasim.scenarios.registry import SCENARIOS
    from materiasim.analysis.registry import ANALYZERS
    groups = dict(engine=ENGINES, builder=BUILDERS, scenario=SCENARIOS, analyzer=ANALYZERS)
    from materiasim.engines.gromacs.specification import BUILDERS as NATIVE_BINDINGS
    entries = {f"{kind}:{name}": dict(id=f"{kind}:{name}", kind=kind, contract_version=1,
                                    requires=[], conflicts=[], python_packages=[])
               for kind, values in groups.items() for name in sorted(values)}
    if set(BUILDERS) != set(NATIVE_BINDINGS.values()) or set(SCENARIOS) != set(NATIVE_BINDINGS):
        raise MateriaSimError("PLUGIN_CONTRACT_MISMATCH", "Native capability bindings differ", category="capability")
    for key, item in entries.items():
        kind, name = key.split(":", 1)
        if kind != "engine":
            item["requires"].append("engine:gromacs")
        if kind == "scenario":
            item["requires"].append("builder:" + NATIVE_BINDINGS[name])
        if kind in ("engine", "scenario", "builder"):
            item["conflicts"] = sorted(k for k, v in entries.items() if v["kind"] == kind and k != key)
        if key in ("analyzer:component_contacts", "analyzer:hydration_contacts"):
            item["python_packages"] = ["MDAnalysis", "numpy"]
    return entries


def required(spec):
    """Return exact registered capabilities needed by one resolved v3 experiment."""
    return {"engine:" + spec["interaction_bundle"]["engine"],
            "builder:" + spec["scenario"]["builder"]["id"],
            "scenario:" + spec["scenario"]["kind"],
            *("analyzer:" + item["kind"] for item in spec["analysis_requests"])}


def resolve(specs, enabled):
    """Validate an explicit allowlist and freeze its actual per-experiment usage and source identity.

    Resolved experiments have already passed native scientific validation. This
    layer narrows usable capabilities; it never makes another combination valid.
    """
    entries = catalog()
    if not isinstance(enabled, list) or any(not isinstance(x, str) for x in enabled):
        raise ValueError("capabilities must be an explicit list of built-in IDs")
    if len(set(enabled)) != len(enabled) or not set(enabled) <= entries.keys():
        raise ValueError("Duplicate or unknown built-in capability")
    # A study can enable two builders globally, but an individual task cannot select both.
    order(entries, enabled, check_conflicts=False)
    selections = [order(entries, required(spec)) for spec in specs]
    missing = set().union(*map(set, selections)) - set(enabled)
    if missing:
        raise ValueError(f"Disabled required capabilities: {sorted(missing)}")
    payload = dict(contract_version=1, enabled=sorted(enabled), selections=selections,
                   specification_hashes=[content_hash(spec) for spec in specs],
                   descriptors=[entries[key] for key in sorted(enabled)],
                   implementation=source_identity())
    return dict(payload, composition_hash=content_hash(payload))


def verify(specs, composition):
    """Reject changed code, configuration or registry selection before launching any worker."""
    if resolve(specs, composition["enabled"]) != composition:
        raise ValueError("Frozen capability composition or implementation changed")


def environment(composition):
    """Probe required Python distribution versions only; missing extras cannot silently switch analyzers."""
    from importlib.metadata import PackageNotFoundError, version
    used = set().union(*map(set, composition["selections"]))
    packages = {p for d in composition["descriptors"] if d["id"] in used for p in d["python_packages"]}
    result = {}
    for package in sorted(packages):
        try:
            result[package] = version(package)
        except PackageNotFoundError as error:
            raise MissingDependency(f"Required analysis dependency missing: {package}") from error
    return result
