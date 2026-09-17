"""Real ENOSPC on an isolated 128-MiB macOS image; no MD and no filling the host filesystem."""

import argparse
import errno
import os
import plistlib
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from materiasim.harness import journal, service, snapshots, supervisor
from materiasim.research.plan import external_output
from materiasim.runtime.state import source_identity
from materiasim.storage import write_json


def command(root, name, arguments):
    """Run one explicit hdiutil operation and retain stdout/stderr outside the constrained volume."""
    result = subprocess.run(["/usr/bin/hdiutil", *arguments], capture_output=True, timeout=45)
    (root / (name + ".stdout")).write_bytes(result.stdout)
    (root / (name + ".stderr")).write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(f"hdiutil {name} failed ({result.returncode}); inspect {root}")
    return result.stdout


def exercise(root, mount):
    """Fill only a validated separate bounded filesystem, reject an event write, then verify rollback."""
    usage = shutil.disk_usage(mount)
    if mount.stat().st_dev == root.stat().st_dev or not 64 * 1024**2 < usage.total <= 160 * 1024**2:
        raise ValueError("Refusing to fill anything except the separate bounded acceptance volume")
    repository = Path(__file__).resolve().parents[2]
    sidecar = repository / "studies/zil_count_smoke/automation.json"
    campaign = mount / "campaign"
    grant = dict(contract_version=1, subject="zil_count_smoke_rules", actor="disk-full-acceptance",
        output_root=str(campaign), expires_utc=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        allowed_actions=["execute", "resume"], total_seconds=300, storage_bytes=16777216)
    write_json(root / "authorization.json", grant)
    # This test exercises only storage/control. Native executable identity probes are explicit fixtures.
    with patch("materiasim.engines.gromacs.command.engine_info", return_value={"fixture": "not-executed"}), \
            patch("materiasim.builders.packmol.packmol_info", return_value={"fixture": "not-executed"}):
        snapshots.create(sidecar, root / "authorization.json", campaign)
    filler = mount / "acceptance-owned-filler.bin"
    written = 0
    full = None
    descriptor = os.open(filler, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        # A failed large write may leave enough blocks for SQLite's small rollback journal.
        block = b"f" * os.statvfs(mount).f_frsize
        while written <= 160 * 1024**2:
            try:
                written += os.write(descriptor, block)
            except OSError as error:
                if error.errno != errno.ENOSPC:
                    raise
                full = error.errno
                break
        if full is None:
            raise AssertionError("Bounded volume did not return real ENOSPC")
    finally:
        os.close(descriptor)
    before = journal.status(campaign)
    try:
        service.control(campaign, "pause", "disk-full-pause", before["sequence"])
    except (sqlite3.Error, OSError) as error:
        rejection = dict(type=type(error).__name__, message=str(error))
    else:
        raise AssertionError("Full-volume event write unexpectedly succeeded")
    # Only this program's newly created filler is removed, to permit SQLite's own rollback.
    filler.unlink()
    state = supervisor.reconcile(campaign)
    if state["sequence"] != before["sequence"] or state["status"] != "ready" or state["active"]:
        raise AssertionError("Failed event became durable or created a reservation")
    recovered = service.control(campaign, "pause", "after-recovery", state["sequence"])
    if recovered["status"] != "paused":
        raise AssertionError("Verified journal could not accept a subsequent legitimate control")
    return dict(real_errno=full, filler_bytes=written, volume_bytes=usage.total,
                write_rejection=rejection, rollback_sequence=state["sequence"],
                post_recovery_status=recovered["status"], md_runs=0, filler_removed=True)


def main():
    """Create/mount one fresh image, always attempt normal detach, and retain evidence and image."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This real filesystem acceptance uses macOS hdiutil, not a Linux certification")
    root = external_output(args.output)
    root.mkdir(parents=True, exist_ok=False)
    if shutil.disk_usage(root).free < 1024**3:
        raise ValueError("Need at least 1 GiB host free space before making a 128-MiB test image")
    image, mount = root / "bounded-volume.dmg", root / "mount"
    mount.mkdir()
    report = dict(status="running", implementation=source_identity(), physical_power_loss_tested=False)
    attached = False
    started = time.monotonic()
    try:
        command(root, "create", ["create", "-size", "128m", "-fs", "HFS+", "-volname",
                                 "MateriaSimFaultTest", "-nospotlight", str(image)])
        raw = command(root, "attach", ["attach", str(image), "-mountpoint", str(mount), "-noautoopen", "-plist"])
        attached = True
        entities = plistlib.loads(raw)["system-entities"]
        if str(mount) not in [e.get("mount-point") for e in entities]:
            raise ValueError("Image was not mounted at the exact authorized test path")
        report.update(exercise(root, mount), status="passed")
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        if attached:
            try:
                command(root, "detach", ["detach", str(mount)])
                report["detached"] = True
            except Exception as error:
                report.update(status="failed", detached=False, detach_error=str(error))
        report["elapsed_seconds"] = time.monotonic() - started
        write_json(root / "acceptance.json", report)
    if report["status"] != "passed":
        raise RuntimeError("Acceptance or normal volume detach failed; inspect retained report")
    print(root / "acceptance.json", flush=True)


if __name__ == "__main__":
    main()
