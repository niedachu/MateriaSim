#!/usr/bin/env python3
"""Start or resume the accepted ion-pair GROMACS production workflow."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_RESUME_FILES = ("prod.tpr", "prod.cpt", "prod.xtc", "prod.edr", "prod.log")
STAGE_STATUS = {
    "em": "RUNNING_EM",
    "nvt": "RUNNING_NVT_1NS",
    "npt": "RUNNING_NPT_5NS",
    "prod": "RUNNING_PRODUCTION_10NS",
}


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


def run_gmx(gmx: str, arguments: Sequence[str], run_directory: Path) -> None:
    """Run one GROMACS command in ``run_directory`` and require success."""
    subprocess.run([gmx, *arguments], cwd=run_directory, check=True)


def sha256_file(path: Path) -> str:
    """Return the uppercase SHA-256 digest used by the frozen-input manifest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def set_run_status(run_directory: Path, message: str) -> None:
    """Replace the run status with a UTC timestamp and the supplied message."""
    timestamp = datetime.now(timezone.utc).isoformat()
    (run_directory / "RUN_STATUS.txt").write_text(
        f"{timestamp}  {message}\n",
        encoding="utf-8",
    )


def validate_run_directory(path: Path) -> Path:
    """Resolve a run directory while rejecting a filesystem root target."""
    resolved = path.expanduser().resolve()
    if resolved == Path(resolved.anchor):
        raise ValueError(f"Run directory must not be a filesystem root: {resolved}")
    return resolved


def frozen_inputs(solvated_gro: Path) -> tuple[tuple[Path, str], ...]:
    """Return the accepted source files and their staged filenames."""
    return (
        (PROJECT_ROOT / "formal" / "input" / "system.top", "system.top"),
        (PROJECT_ROOT / "topology" / "cat.itp", "cat.itp"),
        (PROJECT_ROOT / "topology" / "ani.itp", "ani.itp"),
        (PROJECT_ROOT / "topology" / "gaff2_atomtypes.itp", "gaff2_atomtypes.itp"),
        (PROJECT_ROOT / "smoke" / "input" / "em.mdp", "em.mdp"),
        (PROJECT_ROOT / "smoke" / "input" / "nvt.mdp", "nvt.mdp"),
        (PROJECT_ROOT / "smoke" / "input" / "npt.mdp", "npt.mdp"),
        (PROJECT_ROOT / "formal" / "input" / "prod.mdp", "prod.mdp"),
        (solvated_gro, "solvated.gro"),
    )


def stage_frozen_inputs(run_directory: Path, solvated_gro: Path) -> None:
    """Create a new run directory containing inputs and their SHA-256 manifest."""
    if run_directory.exists():
        raise FileExistsError(f"Refusing to overwrite run directory: {run_directory}")
    inputs = frozen_inputs(solvated_gro.expanduser().resolve())
    missing = [source for source, _ in inputs if not source.is_file()]
    if missing:
        formatted = "\n".join(f"  {path}" for path in missing)
        raise FileNotFoundError(f"Frozen inputs are incomplete:\n{formatted}")
    run_directory.mkdir(parents=True)
    for source, destination_name in inputs:
        shutil.copy2(source, run_directory / destination_name)
    manifest = "".join(
        f"{sha256_file(run_directory / destination_name)} *{destination_name}\n"
        for _, destination_name in inputs
    )
    (run_directory / "FROZEN_INPUT_MANIFEST.txt").write_text(
        manifest,
        encoding="utf-8",
    )


def run_stage(
    gmx: str,
    run_directory: Path,
    name: str,
    coordinates: str,
    threads: int,
    checkpoint: str | None = None,
) -> None:
    """Preprocess and run one fresh EM or dynamics stage."""
    set_run_status(run_directory, STAGE_STATUS[name])
    arguments = ["grompp", "-f", f"{name}.mdp", "-c", coordinates]
    if checkpoint is not None:
        arguments.extend(["-t", checkpoint])
    arguments.extend(["-p", "system.top", "-o", f"{name}.tpr", "-maxwarn", "0"])
    run_gmx(gmx, arguments, run_directory)
    run_gmx(
        gmx,
        ["mdrun", "-deffnm", name, "-nt", str(threads), "-pin", "auto", "-cpt", "10"],
        run_directory,
    )


def start_production(
    gmx: str,
    run_directory: Path,
    solvated_gro: Path,
    threads: int,
) -> None:
    """Stage accepted inputs and run EM, NVT, NPT, and 10 ns production."""
    stage_frozen_inputs(run_directory, solvated_gro)
    run_stage(gmx, run_directory, "em", "solvated.gro", threads)
    run_stage(gmx, run_directory, "nvt", "em.gro", threads)
    run_stage(gmx, run_directory, "npt", "nvt.gro", threads, "nvt.cpt")
    run_stage(gmx, run_directory, "prod", "npt.gro", threads, "npt.cpt")
    set_run_status(run_directory, "COMPLETE_PRODUCTION_10NS")


def resume_production(gmx: str, run_directory: Path, threads: int) -> None:
    """Resume an existing production trajectory from its checkpoint."""
    missing = [name for name in REQUIRED_RESUME_FILES if not (run_directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Required production files are missing: {', '.join(missing)}")
    set_run_status(run_directory, "RUNNING_PRODUCTION_10NS_RESUMED")
    run_gmx(
        gmx,
        [
            "mdrun",
            "-deffnm",
            "prod",
            "-cpi",
            "prod.cpt",
            "-append",
            "-nt",
            str(threads),
            "-pin",
            "auto",
            "-cpt",
            "10",
        ],
        run_directory,
    )
    set_run_status(run_directory, "COMPLETE_PRODUCTION_10NS")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the ``start`` or ``resume`` production command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gmx", help="GROMACS executable; defaults to gmx on PATH.")
    parser.add_argument("--threads", type=int, default=8)
    subparsers = parser.add_subparsers(dest="action", required=True)

    start = subparsers.add_parser("start", help="Create a new formal run.")
    start.add_argument("--run-directory", type=Path, required=True)
    start.add_argument("--solvated-gro", type=Path, required=True)

    resume = subparsers.add_parser("resume", help="Resume an existing production stage.")
    resume.add_argument("--run-directory", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the requested production action and record failures in the run."""
    args = parse_args(argv)
    if args.threads < 1:
        raise ValueError("Threads must be at least 1.")
    gmx = resolve_gmx(args.gmx)
    run_directory = validate_run_directory(args.run_directory)
    try:
        if args.action == "start":
            start_production(gmx, run_directory, args.solvated_gro, args.threads)
        else:
            resume_production(gmx, run_directory, args.threads)
    except Exception as error:
        if run_directory.is_dir():
            set_run_status(run_directory, f"FAILED: {error}")
            error_name = "RESUME_ERROR.txt" if args.action == "resume" else "RUN_ERROR.txt"
            (run_directory / error_name).write_text(
                f"{type(error).__name__}: {error}\n",
                encoding="utf-8",
            )
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
