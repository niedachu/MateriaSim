"""Whole-box density and volume from sealed GROMACS energy frames, without mass guessing."""

import csv
import math
import re
from statistics import mean, stdev

from materiasim.engines.gromacs.command import command, engine_info
from materiasim.specs.schema import fields, number
from materiasim.storage import sha256, utc_now


def validate_density(config):
    """Require an explicit GROMACS command and closed absolute-time window in ps."""
    fields(config, ("gromacs_command", "begin_ps", "end_ps"), "mass density")
    if not isinstance(config["gromacs_command"], str) or not config["gromacs_command"].strip():
        raise ValueError("gromacs_command must explicitly locate the analysis executable")
    for key in ("begin_ps", "end_ps"):
        number(config[key], 0, 1e12, key)
    if config["end_ps"] <= config["begin_ps"]:
        raise ValueError("end_ps must exceed begin_ps")


def read_density_frames(path, config):
    """Read named XVG series as (ps, kg/m^3, nm^3); reject partial or irregular windows.

    No atom masses are inferred. Density and volume are native GROMACS terms.
    Series order follows verified legends, not interactive menu indices.
    """
    legends, axes, rows = {}, {}, []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@"):
                axis = re.fullmatch(r'@\s+([xy])axis\s+label\s+"([^"]+)"', line)
                if axis:
                    if axis[1] in axes:
                        raise ValueError("Duplicate energy axis label")
                    axes[axis[1]] = axis[2]
                match = re.fullmatch(r'@\s+s(\d+)\s+legend\s+"([^"]+)"', line)
                if match:
                    index = int(match[1])
                    if index in legends:
                        raise ValueError("Duplicate energy series legend")
                    legends[index] = match[2]
                continue
            values = list(map(float, line.split()))
            if len(values) != 3 or not all(math.isfinite(value) for value in values):
                raise ValueError("Expected finite time and two energy series")
            rows.append(values)
    if set(legends) != {0, 1} or set(legends.values()) != {"Density", "Volume"}:
        raise ValueError("Energy file must provide exactly Density and Volume")
    units = {"Density": "(kg/m^3)", "Volume": "(nm^3)"}
    if axes != {"x": "Time (ps)", "y": ", ".join(units[legends[i]] for i in range(2))}:
        raise ValueError("Energy axes must identify ps, kg/m^3 and nm^3 in series order")
    if len(rows) < 2:
        raise ValueError("At least two density frames are required")
    density_index = next(index + 1 for index, name in legends.items() if name == "Density")
    volume_index = next(index + 1 for index, name in legends.items() if name == "Volume")
    rows = [(row[0], row[density_index], row[volume_index]) for row in rows]
    # Require requested endpoints to exist: no silent acceptance of a shorter file.
    tolerance = 1e-6  # ps; accommodates decimal serialization, not missing frames.
    if (abs(rows[0][0] - config["begin_ps"]) > tolerance
            or abs(rows[-1][0] - config["end_ps"]) > tolerance):
        raise ValueError("Requested density window must match available energy-frame endpoints")
    interval = rows[1][0] - rows[0][0]
    if interval <= 0:
        raise ValueError("Density frame times must strictly increase")
    for index, (time, density, volume) in enumerate(rows):
        if density <= 0 or volume <= 0:
            raise ValueError("Density and volume must be positive")
        if index and (time <= rows[index - 1][0] or not math.isclose(
                time - rows[index - 1][0], interval, rel_tol=1e-5, abs_tol=tolerance)):
            raise ValueError("Density frames must be strictly increasing and equally spaced")
    return rows


def density_statistics(rows):
    """Return arithmetic saved-frame means and sample SD, never a standard error or CI."""
    density, volume = [row[1] for row in rows], [row[2] for row in rows]
    return dict(mean_density_kg_m3=mean(density), mean_volume_nm3=mean(volume),
                frame_sd_density_kg_m3=stdev(density), frame_sd_volume_nm3=stdev(volume))


def mass_density(inputs, config, output, identity):
    """Extract copied EDR with bounded native execution and retain its command/raw evidence.

    ``inputs`` contains only a sealed energy file; ``output`` is an independent
    AnalysisRun directory. The report describes saved-frame statistics only.
    """
    validate_density(config)
    engine = engine_info(config["gromacs_command"])
    raw = output / "density_volume.xvg"
    result = command(engine, ["energy", "-f", inputs["energy"], "-o", raw,
                              "-b", config["begin_ps"], "-e", config["end_ps"],
                              "-dp", "-xvg", "xmgrace"], output, output / "extract-energy",
                     inputs["energy"].parent, seconds=60, stdin="Density\nVolume\n0\n")
    if result["interrupted"]:
        raise ValueError("Density extraction interrupted; partial output is not accepted")
    if sha256(engine["executable"]) != engine["sha256"]:
        raise ValueError("Analysis executable changed during energy extraction")
    rows = read_density_frames(raw, config)
    with (output / "density_volume.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_ps", "density_kg_m3", "volume_nm3"])
        writer.writerows(rows)
    return dict(kind="mass_density", scientific_quality="not_assessed", **density_statistics(rows),
                run_id=identity["run_id"], spec_hash=identity["spec_hash"], created_utc=utc_now(),
                selection=config, frames=len(rows), time_range_ps=[rows[0][0], rows[-1][0]],
                frame_interval_ps=rows[1][0] - rows[0][0],
                normalization="arithmetic mean of equally spaced saved EDR frames; whole periodic box",
                equilibration_discard_ps=None, window_policy="explicit absolute times; equilibration not assessed",
                independent_samples=None, confidence_interval=None, standard_error=None,
                warning="Frame SD is not mean uncertainty. Saved-frame means can differ from native full-precision "
                        "accumulator means. Whole-box density is not a liquid-region or interfacial density.",
                versions=dict(GROMACS=engine["version"], executable_sha256=engine["sha256"]),
                energy_sha256=sha256(inputs["energy"]),
                csv_sha256=sha256(output / "density_volume.csv"), xvg_sha256=sha256(raw),
                command_sha256=sha256(output / "extract-energy/command.json"),
                stdout_sha256=sha256(output / "extract-energy/stdout.log"),
                stderr_sha256=sha256(output / "extract-energy/stderr.log"))


def density_observations(report):
    """Expose only saved-frame whole-box means with explicit SI/nm^3 units."""
    metrics = []
    for key, unit in (("mean_density_kg_m3", "kg/m^3"), ("mean_volume_nm3", "nm^3")):
        number(report[key], 0, 1e15, key)
        metrics.append(dict(metric=key, unit=unit, value=report[key]))
    return dict(normalization=report["normalization"], metrics=metrics)
