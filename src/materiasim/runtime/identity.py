"""Operation-specific source dependency closures and immutable v3 identity records."""

import ast
from pathlib import Path

from materiasim.storage import content_hash, read_json, sha256
from materiasim.specs.schema import fields

ROOTS = {"execution": ("workflows.execute", "engines.registry"),
         "build": ("workflows.build", "builders.registry"), "analysis": ("workflows.analysis",)}


def implementation(operation, package=None):
    """Hash recursively imported project modules, including function-local imports and package initializers.

    ``package`` is an isolated package copy in dependency tests. External packages are tracked by
    native/analysis environment records, not by pretending their Python paths are project modules.
    """
    root = Path(package) if package is not None else Path(__file__).resolve().parents[1]
    pending = ["materiasim." + module for module in ROOTS[operation]]
    seen, result = set(), {}
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        parts = module.split(".")[1:]
        path = root.joinpath(*parts)
        path = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
        if not path.is_file():
            raise ValueError(f"Unresolved implementation dependency: {module}")
        result[path.relative_to(root).as_posix()] = sha256(path)
        for i in range(len(parts)):
            pending.append(".".join(["materiasim", *parts[:i]]))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                pending.extend(a.name for a in node.names if a.name == "materiasim" or a.name.startswith("materiasim."))
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("materiasim"):
                pending.append(node.module)
                for alias in node.names:
                    child = root.joinpath(*node.module.split(".")[1:], alias.name)
                    if child.with_suffix(".py").is_file() or child.is_dir():
                        pending.append(node.module + "." + alias.name)
            elif isinstance(node, ast.ImportFrom) and node.level:
                raise ValueError("Relative project imports require explicit dependency resolution")
    return dict(sorted(result.items()))


def physical_hash(spec):
    """Hash the declared physical experiment separately from analysis selection and execution resources."""
    return content_hash({key: value for key, value in spec.items()
                         if key not in ("id", "analysis_requests", "execution_profile")})


def native_identity(engine):
    """Select immutable native tool identity independently of its filesystem location."""
    return {key: engine[key] for key in ("sha256", "version", "platform")}


def make_identities(root, spec, engine):
    """Record actual build/execution source closures and physical/request/resource identities at creation."""
    return dict(contract_version=1, physical=physical_hash(spec),
                build=dict(implementation=implementation("build"), engine=native_identity(engine),
                           system_hash=content_hash(read_json(root / "build/resolved_system.json"))),
                execution=dict(implementation=implementation("execution"), engine=native_identity(engine),
                               profile_hash=content_hash(spec["execution_profile"])),
                analysis_requests=content_hash(spec["analysis_requests"]))


def verify_identities(root, spec, manifest):
    """Check persisted v3 identity consistency without requiring the current software to match history."""
    identities = manifest["identities"]
    fields(identities, ("contract_version", "physical", "build", "execution", "analysis_requests"), "identities")
    if type(identities["contract_version"]) is not int or identities["contract_version"] != 1:
        raise ValueError("Unsupported identity contract")
    if identities["physical"] != physical_hash(spec) or identities["analysis_requests"] != content_hash(spec["analysis_requests"]):
        raise ValueError("Physical/analysis identity changed")
    if identities["execution"]["profile_hash"] != content_hash(spec["execution_profile"]):
        raise ValueError("Frozen execution profile identity changed")
    if identities["build"]["system_hash"] != content_hash(read_json(root / "build/resolved_system.json")):
        raise ValueError("Built system identity changed")
    for role in ("build", "execution"):
        if identities[role]["engine"] != native_identity(manifest["engine"]):
            raise ValueError("Native tool identity changed")
        if not identities[role]["implementation"]:
            raise ValueError("Missing implementation dependency closure")
