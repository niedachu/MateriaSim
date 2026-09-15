"""Offline sdist/wheel and installed CLI acceptance using already provisioned build dependencies."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import venv
import zipfile

from materiasim.research.plan import external_output
from materiasim.runtime.capacity import copy_file, copy_tree
from materiasim.runtime.state import source_identity
from materiasim.specs.execution import cpu_profile
from materiasim.storage import read_json, sha256, write_json
from materiasim.workflows.migration import load_executable, portable_document


def command(args, cwd, output, name, env, seconds=180):
    """Capture every subprocess with a finite timeout; preserve failure logs and forbid network install flags."""
    result = subprocess.run(list(map(str, args)), cwd=cwd, env=env, text=True, capture_output=True, timeout=seconds)
    (output / (name + ".stdout")).write_text(result.stdout)
    (output / (name + ".stderr")).write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"Packaging acceptance {name} failed; inspect {output}")
    return result.stdout


def main():
    """Build source distributions offline, install only MateriaSim into a fresh venv and run one dry case."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-python", type=Path, required=True)
    args = parser.parse_args()
    output = external_output(args.output)
    output.mkdir(parents=True, exist_ok=False)
    repository = Path(__file__).resolve().parents[2]
    started = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    env.pop("PYTHONPATH", None)
    report = dict(status="running", implementation=source_identity(), scientific_quality="not_assessed",
                  limits=dict(tasks=1, threads=2, wall_seconds=600, storage_bytes=1073741824),
                  not_tested=["Linux", "GPU", "installed analysis extra", "scientific quality"])
    write_json(output / "acceptance.json", report)
    try:
        check = "from importlib.metadata import version; import json; print(json.dumps({n:version(n) for n in ('setuptools','wheel')}))"
        versions = json.loads(command([args.build_python, "-B", "-c", check], output, output, "build-versions", env))
        if versions != {"setuptools": "80.9.0", "wheel": "0.48.0"}:
            raise ValueError("Existing build environment does not match pyproject.toml")
        source = output / "source"
        source.mkdir()
        for name in ("pyproject.toml", "README.md"):
            copy_file(repository / name, source / name)
        (source / "src").mkdir()
        copy_tree(repository / "src/materiasim", source / "src/materiasim")
        dist = output / "dist"
        dist.mkdir()
        script = "from setuptools.build_meta import build_sdist; build_sdist(" + repr(str(dist)) + ")"
        command([args.build_python, "-B", "-c", script], source, output, "sdist", env)
        sdists = list(dist.glob("*.tar.gz"))
        if len(sdists) != 1:
            raise AssertionError("Expected exactly one source distribution")
        command([args.build_python, "-B", "-m", "pip", "wheel", "--no-index", "--no-deps", "--no-build-isolation",
                 "--wheel-dir", dist, sdists[0]], output, output, "wheel-from-sdist", env)
        wheels = list(dist.glob("*.whl"))
        if len(wheels) != 1:
            raise AssertionError("Expected exactly one wheel")
        with zipfile.ZipFile(wheels[0]) as bundle:
            names = bundle.namelist()
            if any(n.endswith((".gro", ".xtc", ".cpt", ".itp", ".top")) for n in names):
                raise AssertionError("Scientific assets/outputs leaked into core wheel")
        installed = output / "installed"
        venv.EnvBuilder(with_pip=False).create(installed)
        python = installed / "bin/python"
        command([args.build_python, "-B", "-m", "pip", "--python", python, "install", "--no-index", "--no-deps", wheels[0]],
                output, output, "install", env)
        probe = "import json,materiasim; from materiasim.runtime.state import source_identity; print(json.dumps(dict(path=materiasim.__file__,identity=source_identity())))"
        loaded = json.loads(command([python, "-B", "-c", probe], output, output, "installed-origin", env))
        if installed not in Path(loaded["path"]).parents or loaded["identity"] != report["implementation"]:
            raise AssertionError("Installed package differs from source or imported the checkout")
        cli = installed / "bin/materiasim"
        for action in ("tools", "capabilities", "doctor"):
            result = json.loads(command([cli, "--json-envelope", action], output, output, action, env))
            if not result["ok"]:
                raise AssertionError("Installed CLI query failed")
        spec, sources, _, _ = load_executable(repository / "examples/packed_zil_dry.json")
        spec["analysis_requests"] = []
        spec["execution_profile"] = cpu_profile()
        inputs = output / "independent-study"
        (inputs / "assets").mkdir(parents=True)
        for name, path in sources.items():
            copy_file(path, inputs / "assets" / name)
        write_json(inputs / "experiment.json", portable_document(spec, {n: "assets/" + n for n in sources}))
        command([cli, "--json-envelope", "validate", inputs / "experiment.json"], output, output, "validate", env)
        built = json.loads(command([cli, "--json-envelope", "build", inputs / "experiment.json", "--run-root", output / "runs"],
                                  output, output, "build", env))
        run = built["result"]["run_dir"]
        completed = json.loads(command([cli, "--json-envelope", "run", run], output, output, "run", env))
        if completed["result"]["status"] != "completed":
            raise AssertionError("Installed execution failed")
        command([cli, "--json-envelope", "status", run], output, output, "status", env)
        report.update(status="passed", build_versions=versions, package_path=loaded["path"], run=run,
                      sdist=dict(path=str(sdists[0]), sha256=sha256(sdists[0])),
                      wheel=dict(path=str(wheels[0]), sha256=sha256(wheels[0])), independent_source_inputs=True)
        if report["implementation"] != source_identity():
            raise AssertionError("Source changed during package acceptance")
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        report["output_bytes"] = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        if report["elapsed_seconds"] >= 600 or report["output_bytes"] >= 1073741824:
            report.update(status="failed", error="Package acceptance budget exhausted")
        write_json(output / "acceptance.json", report)
    if report["status"] != "passed":
        raise RuntimeError(report["error"])
    print(output / "acceptance.json", flush=True)


if __name__ == "__main__":
    main()
