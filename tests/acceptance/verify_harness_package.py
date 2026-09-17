"""Offline wheel-only installation and composition parity; never launch additional MD."""

import argparse
import json
import os
import time
import venv
from pathlib import Path

from materiasim.harness.snapshots import preview
from materiasim.plugins.builtin import catalog
from materiasim.research.plan import external_output
from materiasim.runtime.capacity import copy_file, copy_tree
from materiasim.runtime.state import source_identity
from materiasim.storage import read_json, sha256, write_json
from tests.acceptance.verify_package_delivery import command


def main():
    """Install only the local core wheel in a fresh environment; compare real registry and source hashes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build-python", type=Path, required=True)
    parser.add_argument("--single-campaign", type=Path, required=True)
    args = parser.parse_args()
    output = external_output(args.output)
    output.mkdir(parents=True, exist_ok=False)
    repository = Path(__file__).resolve().parents[2]
    started = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    env.pop("PYTHONPATH", None)
    report = dict(status="running", implementation=source_identity(), md_runs=0,
                  scope="installed discovery and preflight; no installed MD or analysis execution")
    write_json(output / "acceptance.json", report)
    try:
        query = "from importlib.metadata import version; import json; print(json.dumps({n:version(n) for n in ('setuptools','wheel')}))"
        versions = json.loads(command([args.build_python, "-B", "-c", query], output, output, "versions", env))
        if versions != {"setuptools": "80.9.0", "wheel": "0.48.0"}:
            raise ValueError("Existing build tools differ from pyproject.toml")
        source, dist = output / "source", output / "dist"
        source.mkdir()
        dist.mkdir()
        for name in ("pyproject.toml", "README.md"):
            copy_file(repository / name, source / name)
        (source / "src").mkdir()
        copy_tree(repository / "src/materiasim", source / "src/materiasim")
        command([args.build_python, "-B", "-c", "from setuptools.build_meta import build_wheel; build_wheel(" + repr(str(dist)) + ")"],
                source, output, "wheel", env)
        wheels = list(dist.glob("*.whl"))
        if len(wheels) != 1:
            raise AssertionError("Expected exactly one wheel")
        installed = output / "installed"
        venv.EnvBuilder(with_pip=False).create(installed)
        python = installed / "bin/python"
        command([args.build_python, "-B", "-m", "pip", "--python", python, "install", "--no-index", "--no-deps", wheels[0]],
                output, output, "install", env)
        probe = "import materiasim,json; from materiasim.runtime.state import source_identity; print(json.dumps(dict(path=materiasim.__file__,identity=source_identity())))"
        origin = json.loads(command([python, "-B", "-c", probe], output, output, "origin", env))
        if installed not in Path(origin["path"]).parents or origin["identity"] != report["implementation"]:
            raise AssertionError("Installed import leaked checkout or changed implementation")
        cli = installed / "bin/materiasim"
        plugins = json.loads(command([cli, "campaign", "plugins"], output, output, "plugins", env))
        if plugins != catalog():
            raise AssertionError("Installed registry differs from source")
        tools = json.loads(command([cli, "tools"], output, output, "tools", env))
        agent_commands = {"agent-read", "submit-decision", "human-decision", "agent-tick"}
        if not agent_commands.issubset(tools["campaign"]["writes"]):
            raise AssertionError("Installed agent commands are absent or mislabeled read-only")
        for name in sorted(agent_commands):
            command([cli, "campaign", name, "--help"], output, output, name + "-help", env)
        report["agent_commands"] = sorted(agent_commands)
        inputs = output / "inputs"
        inputs.mkdir()
        copy_tree(args.single_campaign.resolve() / "snapshot", inputs / "snapshot")
        sidecar = read_json(repository / "studies/zil_count_smoke/automation.json")
        sidecar["target"] = dict(kind="experiment", path="snapshot/experiment.json")
        write_json(inputs / "automation.json", sidecar)
        checks = [inputs / "automation.json", repository / "studies/zil_count_smoke/automation.json",
                  repository / "studies/mixed_builders_smoke/automation.json"]
        report["composition_hashes"] = []
        for index, path in enumerate(checks):
            result = json.loads(command([cli, "campaign", "preflight", path], output, output, f"preflight-{index}", env))
            if result != preview(path):
                raise AssertionError("Installed resolution differs from source")
            report["composition_hashes"].append(result["composition"]["composition_hash"])
        report.update(status="passed", wheel_sha256=sha256(wheels[0]), package_path=origin["path"], build_versions=versions)
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        write_json(output / "acceptance.json", report)
    print(output / "acceptance.json", flush=True)


if __name__ == "__main__":
    main()
