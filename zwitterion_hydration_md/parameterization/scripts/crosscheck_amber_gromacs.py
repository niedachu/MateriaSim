#!/usr/bin/env python3
"""Compare Amber/OpenMM and GROMACS energy and forces for one vacuum frame."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import MDAnalysis as mda
import numpy as np
from openmm import Platform, VerletIntegrator, unit
from openmm import app


def read_first_xvg_value(path: Path) -> float:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith(("#", "@")):
            fields = line.split()
            if len(fields) < 2:
                raise ValueError(f"Invalid XVG data line: {raw_line}")
            return float(fields[1])
    raise ValueError(f"No data found in {path}")


def openmm_energy_forces(prmtop_path: Path, coordinate_gro: Path) -> tuple[float, np.ndarray]:
    prmtop = app.AmberPrmtopFile(str(prmtop_path))
    coordinate_universe = mda.Universe(str(coordinate_gro))
    coordinates_nm = np.asarray(coordinate_universe.atoms.positions, dtype=float) / 10.0
    system = prmtop.createSystem(
        nonbondedMethod=app.NoCutoff,
        constraints=None,
        rigidWater=False,
        removeCMMotion=False,
    )
    integrator = VerletIntegrator(0.001 * unit.picoseconds)
    platform = Platform.getPlatformByName("Reference")
    context = None
    try:
        from openmm import Context

        context = Context(system, integrator, platform)
        context.setPositions(coordinates_nm * unit.nanometer)
        state = context.getState(getEnergy=True, getForces=True)
        energy = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
        forces = state.getForces(asNumpy=True).value_in_unit(
            unit.kilojoule_per_mole / unit.nanometer
        )
        return float(energy), np.asarray(forces, dtype=float)
    finally:
        if context is not None:
            del context
        del integrator


def gromacs_forces(gro_path: Path, trr_path: Path) -> np.ndarray:
    universe = mda.Universe(str(gro_path), str(trr_path))
    universe.trajectory[0]
    if universe.trajectory.ts.forces is None:
        raise ValueError("GROMACS TRR contains no forces")
    # MDAnalysis exposes GROMACS forces in kJ mol^-1 Angstrom^-1.
    return np.asarray(universe.trajectory.ts.forces, dtype=float) * 10.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prmtop", type=Path, required=True)
    parser.add_argument("--gromacs-gro", type=Path, required=True)
    parser.add_argument("--gromacs-trr", type=Path, required=True)
    parser.add_argument("--gromacs-potential-xvg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    openmm_energy, openmm_forces_array = openmm_energy_forces(
        args.prmtop, args.gromacs_gro
    )
    gromacs_energy = read_first_xvg_value(args.gromacs_potential_xvg)
    gromacs_forces_array = gromacs_forces(args.gromacs_gro, args.gromacs_trr)
    if openmm_forces_array.shape != gromacs_forces_array.shape:
        raise ValueError(
            f"Force shapes differ: {openmm_forces_array.shape} versus {gromacs_forces_array.shape}"
        )

    difference = gromacs_forces_array - openmm_forces_array
    openmm_rms = float(np.sqrt(np.mean(openmm_forces_array**2)))
    difference_rms = float(np.sqrt(np.mean(difference**2)))
    report = {
        "comparison": "Same coordinates; vacuum; no constraints; all pair interactions; no dispersion correction",
        "atom_count": int(openmm_forces_array.shape[0]),
        "energy_kJ_mol": {
            "openmm_amber": openmm_energy,
            "gromacs": gromacs_energy,
            "signed_difference_gromacs_minus_openmm": gromacs_energy - openmm_energy,
            "absolute_difference": abs(gromacs_energy - openmm_energy),
        },
        "forces_kJ_mol_nm": {
            "openmm_rms_component": openmm_rms,
            "difference_rms_component": difference_rms,
            "relative_rms_difference": difference_rms / openmm_rms,
            "maximum_absolute_component_difference": float(np.max(np.abs(difference))),
            "all_finite": bool(
                np.all(np.isfinite(openmm_forces_array))
                and np.all(np.isfinite(gromacs_forces_array))
            ),
        },
        "software": {
            "openmm_platform": "Reference",
            "force_units_after_conversion": "kJ mol^-1 nm^-1",
        },
    }
    if not math.isfinite(openmm_energy) or not math.isfinite(gromacs_energy):
        raise ValueError("Non-finite potential energy")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
