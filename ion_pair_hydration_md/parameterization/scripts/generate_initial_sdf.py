#!/usr/bin/env python3
"""Generate one explicit-hydrogen 3D SDF conformer from a charged SMILES."""

from __future__ import annotations

import argparse
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import AllChem


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smiles", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    molecule = Chem.MolFromSmiles(args.smiles)
    if molecule is None:
        raise ValueError("invalid SMILES")
    molecule = Chem.AddHs(molecule)
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = args.seed
    parameters.useRandomCoords = True
    if AllChem.EmbedMolecule(molecule, parameters) != 0:
        raise RuntimeError("RDKit could not embed a 3D conformer")
    try:
        AllChem.MMFFOptimizeMolecule(molecule, mmffVariant="MMFF94s", maxIters=1000)
    except Exception:
        AllChem.UFFOptimizeMolecule(molecule, maxIters=1000)
    molecule.SetProp("_Name", args.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Chem.MolToMolFile(molecule, str(args.output))


if __name__ == "__main__":
    main()

