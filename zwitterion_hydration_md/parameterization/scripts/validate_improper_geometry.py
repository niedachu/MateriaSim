#!/usr/bin/env python3
"""Compare GAFF2-minimized imidazolium geometry with existing QM structures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from rdkit import Chem


RING = np.array([5, 6, 7, 15, 16])
RING_BONDS = [(5, 6), (6, 7), (7, 15), (15, 16), (16, 5)]
IMPROPERS = [
    (4, 6, 5, 16),
    (8, 6, 7, 15),
    (25, 5, 6, 7),
    (16, 37, 15, 7),
    (15, 38, 16, 5),
]


def read_sdf_coordinates_nm(path: Path) -> np.ndarray:
    molecule = Chem.MolFromMolFile(str(path), removeHs=False, sanitize=False)
    if molecule is None or molecule.GetNumAtoms() != 39:
        raise ValueError(f"Expected 39 atoms in {path}")
    return np.asarray(molecule.GetConformer().GetPositions(), dtype=float) / 10.0


def read_gro_coordinates_nm(path: Path) -> np.ndarray:
    lines = path.read_text(encoding="utf-8").splitlines()
    if int(lines[1].strip()) != 39:
        raise ValueError(f"Expected 39 atoms in {path}")
    return np.asarray(
        [
            [float(line[20:28]), float(line[28:36]), float(line[36:44])]
            for line in lines[2:41]
        ],
        dtype=float,
    )


def plane_metrics(coordinates: np.ndarray) -> dict[str, float]:
    selected = coordinates[RING]
    centered = selected - selected.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    distances = centered @ vh[-1]
    return {
        "rms_nm": float(np.sqrt(np.mean(distances**2))),
        "maximum_nm": float(np.max(np.abs(distances))),
    }


def kabsch_rmsd_nm(reference: np.ndarray, mobile: np.ndarray) -> float:
    reference_centered = reference - reference.mean(axis=0)
    mobile_centered = mobile - mobile.mean(axis=0)
    covariance = mobile_centered.T @ reference_centered
    left, _, right = np.linalg.svd(covariance)
    correction = np.eye(3)
    correction[-1, -1] = np.sign(np.linalg.det(left @ right))
    rotation = left @ correction @ right
    aligned = mobile_centered @ rotation
    return float(np.sqrt(np.mean(np.sum((aligned - reference_centered) ** 2, axis=1))))


def dihedral_degrees(points: np.ndarray) -> float:
    p0, p1, p2, p3 = points
    b0 = -(p1 - p0)
    b1 = p2 - p1
    b2 = p3 - p2
    b1 /= np.linalg.norm(b1)
    v = b0 - np.dot(b0, b1) * b1
    w = b2 - np.dot(b2, b1) * b1
    return float(np.degrees(np.arctan2(np.dot(np.cross(b1, v), w), np.dot(v, w))))


def nonplanarity_degrees(angle: float) -> float:
    absolute = abs(angle)
    return min(absolute, abs(180.0 - absolute))


def bond_lengths_nm(coordinates: np.ndarray) -> list[float]:
    return [float(np.linalg.norm(coordinates[a] - coordinates[b])) for a, b in RING_BONDS]


def summarize_structure(coordinates: np.ndarray) -> dict[str, object]:
    angles = [dihedral_degrees(coordinates[list(indices)]) for indices in IMPROPERS]
    return {
        "ring_plane": plane_metrics(coordinates),
        "ring_bond_lengths_nm": bond_lengths_nm(coordinates),
        "improper_angles_degrees": angles,
        "improper_nonplanarity_degrees": [nonplanarity_degrees(value) for value in angles],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qm-dir", type=Path, required=True)
    parser.add_argument("--minimized-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    thresholds = {
        "ring_kabsch_rmsd_nm": 0.02,
        "maximum_ring_plane_deviation_nm": 0.02,
        "maximum_improper_nonplanarity_degrees": 15.0,
        "ring_bond_minimum_nm": 0.125,
        "ring_bond_maximum_nm": 0.150,
    }
    records = {}
    all_passed = True
    for label in ("extended", "intermediate", "folded"):
        qm = read_sdf_coordinates_nm(args.qm_dir / f"zil_{label}.sdf")
        minimized = read_gro_coordinates_nm(args.minimized_dir / f"{label}_min.gro")
        qm_summary = summarize_structure(qm)
        minimized_summary = summarize_structure(minimized)
        ring_rmsd = kabsch_rmsd_nm(qm[RING], minimized[RING])
        minimized_bonds = minimized_summary["ring_bond_lengths_nm"]
        checks = {
            "ring_kabsch_rmsd": ring_rmsd <= thresholds["ring_kabsch_rmsd_nm"],
            "ring_plane": minimized_summary["ring_plane"]["maximum_nm"]
            <= thresholds["maximum_ring_plane_deviation_nm"],
            "improper_planarity": max(minimized_summary["improper_nonplanarity_degrees"])
            <= thresholds["maximum_improper_nonplanarity_degrees"],
            "ring_bond_range": min(minimized_bonds) >= thresholds["ring_bond_minimum_nm"]
            and max(minimized_bonds) <= thresholds["ring_bond_maximum_nm"],
        }
        passed = all(checks.values())
        all_passed = all_passed and passed
        records[label] = {
            "qm_hf_6_31g_star": qm_summary,
            "gaff2_minimized": minimized_summary,
            "ring_kabsch_rmsd_nm": ring_rmsd,
            "checks": checks,
            "passed": passed,
        }

    report = {
        "reference": "Existing gas-phase HF/6-31G* optimized PsiRESP geometries; RESP charges are not used",
        "improper_atom_indices_1_based": [
            [index + 1 for index in indices] for indices in IMPROPERS
        ],
        "thresholds": thresholds,
        "conformers": records,
        "all_conformers_passed": all_passed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
