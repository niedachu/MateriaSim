"""Explicit whole-workflow resource contract, independent of physical MD parameters."""

from materiasim.specs.schema import fields, integer, number

COMMON = ("contract_version", "device", "threads", "max_wall_seconds", "total_wall_seconds",
          "max_attempts", "checkpoint_interval_minutes")
EXTRA = ("build_seconds", "analysis_seconds", "workflow_seconds", "termination_grace_seconds",
         "storage_bytes", "min_free_bytes", "gpu_id", "dynamics_offload")


def validate_profile(value):
    """Validate v2 engineering ceilings or v3 explicit tools and finite non-smoke allocations."""
    version = value.get("contract_version") if isinstance(value, dict) else None
    fields(value, COMMON + EXTRA + (("tools",) if version == 3 else ()), "execution_profile")
    integer(version, 2, 3, "profile version")
    if version == 3:
        fields(value["tools"], ("gmx", "packmol"), "tools")
        for locator in value["tools"].values():
            if not isinstance(locator, str) or not locator.strip() or "\x00" in locator:
                raise ValueError("Tool locators must be nonempty executable names or paths")
    if value["device"] not in ("cpu", "gpu"):
        raise ValueError("Explicit cpu/gpu device required")
    integer(value["threads"], 1, 8, "threads")
    integer(value["max_attempts"], 1, 8, "max_attempts")
    number(value["checkpoint_interval_minutes"], .001, 10, "checkpoint interval")
    for key, limit in (("max_wall_seconds", 600), ("total_wall_seconds", 1800),
                       ("build_seconds", 600), ("analysis_seconds", 120), ("workflow_seconds", 3600)):
        number(value[key], 1, limit if version == 2 else 604800, key)
    number(value["termination_grace_seconds"], 25, 60, "termination_grace_seconds")
    if value["total_wall_seconds"] < max(26, value["max_wall_seconds"]):
        raise ValueError("Execution total must cover an attempt and stopping grace")
    if value["workflow_seconds"] < max(value["build_seconds"], value["max_wall_seconds"], value["analysis_seconds"]) + value["termination_grace_seconds"]:
        raise ValueError("Workflow total must cover its largest operation plus grace")
    integer(value["storage_bytes"], 1048576, 1073741824 if version == 2 else 1099511627776, "storage_bytes")
    integer(value["min_free_bytes"], 67108864, 1073741824, "min_free_bytes")
    fields(value["dynamics_offload"], ("nb", "pme", "bonded", "update"), "dynamics_offload")
    if any(policy not in ("cpu", "gpu") for policy in value["dynamics_offload"].values()):
        raise ValueError("Offload requires explicit cpu/gpu, never auto or shell options")
    if value["device"] == "cpu":
        if value["gpu_id"] is not None or any(v != "cpu" for v in value["dynamics_offload"].values()):
            raise ValueError("CPU profile cannot request a GPU ID or offload")
    else:
        integer(value["gpu_id"], 0, 63, "gpu_id")
        if value["dynamics_offload"]["nb"] != "gpu":
            raise ValueError("GPU execution requires explicit nonbonded GPU work")
        # First local implementation uses the well-bounded force-offload path.
        # Additional offloads need their native constraint/log compatibility checks.
        if any(value["dynamics_offload"][k] != "cpu" for k in ("bonded", "update")):
            raise ValueError("Bonded/update GPU offload is not implemented in this profile contract")


def cpu_profile():
    """Return the explicit v2 engineering example budget, not a production allocation."""
    return dict(contract_version=2, device="cpu", threads=2, max_wall_seconds=180,
                total_wall_seconds=360, max_attempts=2, checkpoint_interval_minutes=.01,
                build_seconds=600, analysis_seconds=120, workflow_seconds=1200,
                termination_grace_seconds=25, storage_bytes=536870912, min_free_bytes=67108864,
                gpu_id=None, dynamics_offload=dict(nb="cpu", pme="cpu", bonded="cpu", update="cpu"))
