#!/usr/bin/env python3
"""Run the accepted ZIL production protocol on macOS or Linux.

The runner validates frozen topology hashes, stages one directory per
replicate, and resumes any stage that already has a checkpoint. It calls the
native ``gmx`` executable directly and does not require a shell-specific
runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFORMER_FILES = {
    "extended": "zil_extended.gro",
    "intermediate": "zil_intermediate.gro",
    "folded": "zil_folded.gro",
}
FORMAL_TOPOLOGY_FILES = (
    "zil.itp",
    "system.top",
    "zil_extended.gro",
    "zil_intermediate.gro",
    "zil_folded.gro",
)


def resolve_gmx(candidate: str | None) -> str:
    """Resolve an explicit GROMACS executable or find ``gmx`` on ``PATH``."""
    command = candidate or "gmx"
    explicit = Path(command).expanduser()
    if explicit.is_file():
        return str(explicit.resolve())
    resolved = shutil.which(command)
    if resolved is None:
        raise FileNotFoundError(
            "GROMACS was not found; install gmx on PATH or pass --gmx."
        )
    return resolved


def run_gmx(gmx: str, arguments: Sequence[str], cwd: Path) -> None:
    """Run one GROMACS command in ``cwd`` and fail on a non-zero exit code."""
    subprocess.run([gmx, *arguments], cwd=cwd, check=True)


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of ``path``."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from ``path`` and reject non-object roots."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    """Write JSON through a sibling temporary file to avoid partial manifests."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def assert_no_placeholder(path: Path) -> None:
    """Reject unresolved uppercase placeholders in a formal input file."""
    if re.search(r"<[A-Z_]+>", path.read_text(encoding="utf-8")):
        raise ValueError(f"Placeholder text remains in formal input: {path}")


def set_nvt_seed(source: Path, destination: Path, seed: int) -> None:
    """Copy an NVT MDP while replacing its velocity-generation seed."""
    content = source.read_text(encoding="utf-8")
    updated, replacements = re.subn(
        r"(?m)^gen-seed\s*=.*$",
        f"gen-seed                 = {seed}",
        content,
    )
    if replacements == 0:
        raise ValueError(f"No gen-seed setting found in {source}")
    destination.write_text(updated, encoding="utf-8")


def validate_protocol(project_root: Path) -> tuple[dict[str, Any], list[str], float]:
    """Validate frozen project inputs and return execution settings.

    The return value contains the simulation config, accepted ``mdrun``
    arguments, and checkpoint interval in minutes.
    """
    topology_dir = project_root / "topology"
    mdp_dir = project_root / "mdp"
    config_path = project_root / "config" / "simulation_config.json"
    acceptance_path = project_root / "results" / "acceptance" / "ACCEPTED.json"
    required = [
        config_path,
        acceptance_path,
        *(topology_dir / name for name in FORMAL_TOPOLOGY_FILES),
        *(mdp_dir / name for name in ("em.mdp", "nvt.mdp", "npt.mdp", "prod.mdp")),
    ]
    missing = [path for path in required if not path.is_file()]
    if missing:
        formatted = "\n".join(f"  {path}" for path in missing)
        raise FileNotFoundError(f"Formal production inputs are incomplete:\n{formatted}")

    config = read_json(config_path)
    acceptance = read_json(acceptance_path)
    if acceptance.get("status") != "accepted":
        raise ValueError("Acceptance status is not accepted; production is blocked.")
    accepted_arguments = acceptance.get("mdrun_arguments")
    if not isinstance(accepted_arguments, list):
        raise ValueError("Acceptance record does not contain mdrun_arguments.")
    checkpoint_minutes = float(config["production"]["checkpoint_interval_min"])
    if checkpoint_minutes <= 0:
        raise ValueError("checkpoint_interval_min must be positive.")
    if acceptance.get("charge_model") != config["solute"]["charge_model"]:
        raise ValueError("Acceptance charge model does not match the simulation config.")

    accepted_hashes = acceptance.get("topology_sha256")
    if not isinstance(accepted_hashes, dict):
        raise ValueError("Acceptance record does not contain topology_sha256.")
    for name in FORMAL_TOPOLOGY_FILES:
        expected = str(accepted_hashes.get(name, "")).lower()
        if not expected or sha256_file(topology_dir / name) != expected:
            raise ValueError(f"Formal topology hash does not match acceptance: {name}")

    system_topology = topology_dir / "system.top"
    assert_no_placeholder(system_topology)
    assert_no_placeholder(topology_dir / "zil.itp")
    if re.search(
        r"(?m)^\s*SOL\s+0\s*(?:;.*)?$",
        system_topology.read_text(encoding="utf-8"),
    ):
        raise ValueError("Formal system.top must omit SOL before solvation.")
    return config, [str(value) for value in accepted_arguments], checkpoint_minutes


def validate_run_root(run_root: Path) -> Path:
    """Resolve ``run_root`` while rejecting a filesystem root as a target."""
    resolved = run_root.expanduser().resolve()
    if resolved == Path(resolved.anchor):
        raise ValueError(f"Run root must not be a filesystem root: {resolved}")
    return resolved


def stage_inputs(
    project_root: Path,
    run_dir: Path,
    config: dict[str, Any],
    replicate: dict[str, Any],
) -> Path:
    """Create or validate a replicate input manifest and return its input dir."""
    replicate_id = str(replicate["id"])
    conformer = str(replicate["starting_conformer"])
    if conformer not in CONFORMER_FILES:
        raise ValueError(f"Unknown starting conformer '{conformer}' for {replicate_id}")
    input_dir = run_dir / "input"
    manifest_path = run_dir / "input_manifest.json"
    if run_dir.exists() and not manifest_path.is_file():
        raise ValueError(f"Refusing to use an unrecognized run directory: {run_dir}")
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        if (
            manifest.get("project_id") != config["project_id"]
            or manifest.get("replicate_id") != replicate_id
        ):
            raise ValueError(f"Run manifest does not match the requested run: {manifest_path}")
        return input_dir

    input_dir.mkdir(parents=True)
    topology_dir = project_root / "topology"
    mdp_dir = project_root / "mdp"
    for name in ("zil.itp", "system.top", CONFORMER_FILES[conformer]):
        shutil.copy2(topology_dir / name, input_dir / name)
    for name in ("em.mdp", "npt.mdp", "prod.mdp"):
        shutil.copy2(mdp_dir / name, input_dir / name)
    set_nvt_seed(mdp_dir / "nvt.mdp", input_dir / "nvt.mdp", int(replicate["velocity_seed"]))
    source_files = [
        {"name": path.name, "sha256": sha256_file(path)}
        for path in sorted(input_dir.iterdir(), key=lambda item: item.name)
        if path.is_file()
    ]
    write_json_atomic(
        manifest_path,
        {
            "project_id": str(config["project_id"]),
            "replicate_id": replicate_id,
            "starting_conformer": conformer,
            "velocity_seed": int(replicate["velocity_seed"]),
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_files": source_files,
        },
    )
    return input_dir


def run_mdrun(
    gmx: str,
    run_dir: Path,
    deffnm: str,
    threads: int,
    accepted_arguments: Sequence[str],
    checkpoint_minutes: float,
) -> None:
    """Run or resume one accepted ``mdrun`` stage."""
    arguments = [
        "mdrun",
        "-deffnm",
        deffnm,
        "-ntmpi",
        "1",
        "-ntomp",
        str(threads),
        "-cpt",
        str(checkpoint_minutes),
        *accepted_arguments,
    ]
    checkpoint = run_dir / f"{deffnm}.cpt"
    if checkpoint.is_file():
        arguments.extend(["-cpi", checkpoint.name, "-append"])
    run_gmx(gmx, arguments, run_dir)


def run_replicate(
    gmx: str,
    project_root: Path,
    run_root: Path,
    config: dict[str, Any],
    replicate: dict[str, Any],
    threads: int,
    accepted_arguments: Sequence[str],
    checkpoint_minutes: float,
) -> None:
    """Execute all missing stages for one configured replicate."""
    run_dir = run_root / str(replicate["id"])
    input_dir = stage_inputs(project_root, run_dir, config, replicate)
    conformer = CONFORMER_FILES[str(replicate["starting_conformer"])]
    run_topology = input_dir / "system.top"

    if not (run_dir / "solvated.gro").is_file():
        run_gmx(
            gmx,
            ["editconf", "-f", str(input_dir / conformer), "-o", "boxed.gro", "-c", "-box", "4.5", "4.5", "4.5"],
            run_dir,
        )
        run_gmx(
            gmx,
            ["solvate", "-cp", "boxed.gro", "-cs", "spc216.gro", "-o", "solvated.gro", "-p", str(run_topology)],
            run_dir,
        )
    stages = (
        ("em", "solvated.gro", None),
        ("nvt", "em.gro", None),
        ("npt", "nvt.gro", "nvt.cpt"),
        ("prod", "npt.gro", "npt.cpt"),
    )
    for name, coordinates, checkpoint in stages:
        if not (run_dir / f"{name}.tpr").is_file():
            arguments = [
                "grompp",
                "-f",
                str(input_dir / f"{name}.mdp"),
                "-c",
                coordinates,
            ]
            if checkpoint is not None:
                arguments.extend(["-t", checkpoint])
            arguments.extend(["-p", str(run_topology), "-o", f"{name}.tpr", "-maxwarn", "0"])
            run_gmx(gmx, arguments, run_dir)
        if not (run_dir / f"{name}.gro").is_file():
            run_mdrun(
                gmx,
                run_dir,
                name,
                threads,
                accepted_arguments,
                checkpoint_minutes,
            )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the cross-platform production command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gmx", help="GROMACS executable; defaults to gmx on PATH.")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the accepted protocol and execute every configured replicate."""
    args = parse_args(argv)
    if args.threads < 1:
        raise ValueError("Threads must be at least 1.")
    gmx = resolve_gmx(args.gmx)
    run_root = validate_run_root(args.run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    config, accepted_arguments, checkpoint_minutes = validate_protocol(PROJECT_ROOT)
    for replicate in config["production"]["replicates"]:
        run_replicate(
            gmx,
            PROJECT_ROOT,
            run_root,
            config,
            replicate,
            args.threads,
            accepted_arguments,
            checkpoint_minutes,
        )
    print("All configured formal production trajectories completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
