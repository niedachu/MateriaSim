#!/usr/bin/env python3
"""Assemble retained fragment RESP charges into two complete 39-atom candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from validate_parameters import summarize_atomic_charges


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_retained(path: Path) -> dict[int, tuple[str, float]]:
    result: dict[int, tuple[str, float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            index = int(row["target_atom_index_zero_based"])
            if index in result:
                raise ValueError(f"duplicate target atom {index} in {path}")
            result[index] = (row["element"], float(row["resp_charge_e"]))
    if not result:
        raise ValueError(f"no retained charges in {path}")
    return result


def require_fragment_metadata(path: Path) -> dict[str, Any]:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if metadata.get("status") != "fragment_resp_complete_pending_assembly":
        raise ValueError(f"fragment RESP is not eligible for assembly: {path}")
    return metadata


def assemble_scheme(
    scheme: str,
    fragment_base: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> tuple[list[str], list[float], dict[str, Any]]:
    combined: dict[int, tuple[str, float]] = {}
    inputs: dict[str, dict[str, str]] = {}
    for fragment in ("sulfonate", "imidazolium", "ether"):
        directory = fragment_base / scheme / fragment
        metadata_path = directory / "fragment_resp_metadata.json"
        charge_path = directory / "retained_charges.csv"
        require_fragment_metadata(metadata_path)
        charges = read_retained(charge_path)
        overlap = set(combined) & set(charges)
        if overlap:
            raise ValueError(f"fragment target mappings overlap: {sorted(overlap)}")
        combined.update(charges)
        inputs[fragment] = {
            "metadata_sha256": sha256(metadata_path),
            "retained_charges_sha256": sha256(charge_path),
        }
    expected_count = int(config["target"]["expected_atom_count_with_hydrogens"])
    if sorted(combined) != list(range(expected_count)):
        raise ValueError(f"scheme {scheme} does not cover all {expected_count} target atoms")
    elements = [combined[index][0] for index in range(expected_count)]
    charges = [combined[index][1] for index in range(expected_count)]
    validation = summarize_atomic_charges(
        charges,
        expected_charge=float(config["target"]["formal_charge_e"]),
        net_charge_tolerance=float(config["validation"]["net_charge_tolerance_e"]),
        max_abs_atomic_charge=float(config["validation"]["max_abs_atomic_charge_e"]),
    )
    scheme_dir = output_dir / scheme
    scheme_dir.mkdir(parents=True, exist_ok=True)
    csv_path = scheme_dir / "assembled_charges.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["target_atom_index_zero_based", "element", "resp_charge_e"])
        for index, (element, charge) in enumerate(zip(elements, charges)):
            writer.writerow([index, element, f"{charge:.10f}"])
    text_path = scheme_dir / "assembled_charges.txt"
    text_path.write_text("\n".join(f"{charge:.10f}" for charge in charges) + "\n", encoding="utf-8")
    metadata = {
        "status": (
            "assembled_candidate_pending_full_molecule_validation"
            if validation["passed_conservative_magnitude_screen"]
            else "assembled_candidate_rejected_unphysical_charges"
        ),
        "scheme": scheme,
        "atom_count": expected_count,
        "total_charge_e": math.fsum(charges),
        "charge_validation": validation,
        "inputs": inputs,
        "outputs": {
            csv_path.name: sha256(csv_path),
            text_path.name: sha256(text_path),
        },
    }
    metadata_path = scheme_dir / "assembled_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    if metadata["status"] != "assembled_candidate_pending_full_molecule_validation":
        raise ValueError(f"assembled scheme {scheme} failed the atomic-charge screen")
    return elements, charges, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--fragment-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = {}
    for scheme in ("methyl", "ethyl"):
        elements, charges, metadata = assemble_scheme(
            scheme,
            args.fragment_results.resolve(),
            output_dir,
            config,
        )
        candidates[scheme] = {"elements": elements, "charges": charges, "metadata": metadata}
    if candidates["methyl"]["elements"] != candidates["ethyl"]["elements"]:
        raise ValueError("methyl and ethyl candidates have different element order")

    differences = [
        methyl - ethyl
        for methyl, ethyl in zip(
            candidates["methyl"]["charges"], candidates["ethyl"]["charges"]
        )
    ]
    key_indices = {
        int(value)
        for value in config["validation"]["key_target_heavy_atom_indices_zero_based"]
    }
    key_max = max(abs(differences[index]) for index in key_indices)
    rms = math.sqrt(math.fsum(value * value for value in differences) / len(differences))
    key_trigger = float(
        config["validation"]["cap_scheme_key_atom_difference_review_trigger_e"]
    )
    rms_trigger = float(
        config["validation"]["cap_scheme_all_atom_rms_difference_review_trigger_e"]
    )
    comparison_csv = output_dir / "methyl_vs_ethyl_difference.csv"
    with comparison_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "target_atom_index_zero_based",
                "element",
                "methyl_charge_e",
                "ethyl_charge_e",
                "methyl_minus_ethyl_e",
                "key_atom",
            ]
        )
        for index, difference in enumerate(differences):
            writer.writerow(
                [
                    index,
                    candidates["methyl"]["elements"][index],
                    f"{candidates['methyl']['charges'][index]:.10f}",
                    f"{candidates['ethyl']['charges'][index]:.10f}",
                    f"{difference:.10f}",
                    index in key_indices,
                ]
            )
    requires_review = key_max > key_trigger or rms > rms_trigger
    report = {
        "status": "cap_scheme_sensitivity_requires_review" if requires_review else "cap_scheme_sensitivity_passed",
        "selection_status": "no_candidate_selected_pending_full_molecule_esp_and_dipole_review",
        "maximum_key_atom_difference_e": key_max,
        "all_atom_rms_difference_e": rms,
        "key_atom_review_trigger_e": key_trigger,
        "all_atom_rms_review_trigger_e": rms_trigger,
        "comparison_csv": comparison_csv.name,
        "comparison_csv_sha256": sha256(comparison_csv),
        "config_sha256": sha256(config_path),
    }
    report_path = output_dir / "assembly_comparison_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
