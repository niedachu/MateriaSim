"""Explicit single-CUDA-device selection and native offload evidence; no CPU fallback."""

import csv
import os
import re
import shutil
import subprocess

from materiasim.errors import MateriaSimError


def build_capabilities(output):
    """Extract advertised GPU/MPI build properties; unrecognized output remains unknown."""
    result = {}
    for key, label in (("gpu", "GPU support"), ("mpi", "MPI library")):
        match = re.search(r"^" + label + r":\s*(.+)$", output, re.M)
        result[key] = match.group(1).strip() if match else "unknown"
    return result


def visible_devices():
    """Query driver UUIDs and honor explicit CUDA visibility without changing global environment."""
    candidate = shutil.which("nvidia-smi")
    if candidate is None:
        return dict(status="unknown", reason="nvidia-smi unavailable", devices=[])
    try:
        response = subprocess.run([candidate, "--query-gpu=index,uuid,name", "--format=csv,noheader"],
                                  capture_output=True, text=True, check=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as error:
        return dict(status="unknown", reason=type(error).__name__, devices=[])
    devices = []
    for row in csv.reader(response.stdout.splitlines()):
        if len(row) != 3 or not row[0].strip().isdigit() or not re.fullmatch(r"GPU-[0-9a-fA-F-]+", row[1].strip()):
            return dict(status="unknown", reason="unrecognized driver inventory", devices=[])
        devices.append(dict(driver_index=int(row[0]), uuid=row[1].strip(), name=row[2].strip()))
    visibility = os.environ.get("CUDA_VISIBLE_DEVICES")
    if visibility is not None:
        selected = []
        for token in visibility.split(",") if visibility.strip() else []:
            token = token.strip()
            matches = [item for item in devices if str(item["driver_index"]) == token or item["uuid"] == token]
            if len(matches) != 1 or matches[0] in selected:
                return dict(status="unknown", reason="unsupported CUDA visibility (MIG/abbreviations excluded)", devices=[])
            selected.append(matches[0])
        devices = selected
    return dict(status="available" if devices else "unavailable", devices=devices)


def resolve_device(profile, engine):
    """Require CPU capacity or a CUDA/thread-MPI build and an explicitly visible full GPU UUID."""
    if profile["threads"] > (os.cpu_count() or 1):
        raise MateriaSimError("MISSING_RESOURCE", "Requested CPU threads exceed visible logical CPUs", category="environment")
    if profile["device"] == "cpu":
        return dict(device="cpu", gpu_used=False)
    capabilities = engine.get("build_capabilities", {})
    if capabilities.get("gpu", "").upper() != "CUDA" or capabilities.get("mpi") != "thread_mpi":
        raise MateriaSimError("UNSUPPORTED_COMBINATION", "GPU execution requires a CUDA/thread_mpi GROMACS build", category="environment")
    inventory = visible_devices()
    if inventory["status"] != "available" or profile["gpu_id"] >= len(inventory["devices"]):
        raise MateriaSimError("MISSING_RESOURCE", "Requested GPU is unavailable or device identity is unknown", category="environment")
    item = inventory["devices"][profile["gpu_id"]]
    return dict(device="gpu", backend="CUDA", visible_index=profile["gpu_id"], selected_uuid=item["uuid"],
                name=item["name"], native_gpu_id=0,
                environment=dict(CUDA_VISIBLE_DEVICES=item["uuid"]))


def offload_arguments(profile, stage):
    """Build explicit native flags; minimization always uses the declared CPU preparation policy."""
    policy = (profile["dynamics_offload"] if stage["type"] == "dynamics" else
              dict(nb="cpu", pme="cpu", bonded="cpu", update="cpu"))
    result = [item for key in ("nb", "pme", "bonded", "update") for item in ("-" + key, policy[key])]
    if policy["nb"] == "gpu":
        result.extend(["-gpu_id", "0"])
    return result, policy


def verify_offload(text, policy):
    """Check this attempt's native startup report, not an old appended log or GPU utilization guess."""
    pp = re.findall(r"^PP tasks will do .*short-ranged.* interactions on the GPU\s*$", text, re.M)
    pme = re.findall(r"^PME tasks will do all aspects on the GPU\s*$", text, re.M)
    mappings = re.findall(r"\b(PP|PME):(\d+)\b", text)
    if policy["nb"] == "gpu":
        if not pp or ("PP", "0") not in mappings or any(index != "0" for _, index in mappings):
            raise ValueError("Missing or conflicting native GPU nonbonded/mapping evidence")
    elif pp or mappings:
        raise ValueError("CPU stage unexpectedly reported GPU work")
    if (policy["pme"] == "gpu") != bool(pme):
        raise ValueError("Native PME offload evidence differs from requested policy")
    if policy["pme"] == "gpu" and ("PME", "0") not in mappings:
        raise ValueError("Missing PME GPU task mapping")
    if re.search(r"most bonded interactions on the GPU|update and constrain coordinates on the GPU", text):
        raise ValueError("Native bonded/update GPU work conflicts with CPU-only policy")
    return dict(policy=policy, gpu_used=bool(pp), evidence="native_startup_report")
