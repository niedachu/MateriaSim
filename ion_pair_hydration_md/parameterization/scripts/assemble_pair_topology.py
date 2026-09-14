#!/usr/bin/env python3
"""Assemble separate CAT/ANI GROMACS molecule types into a neutral pair topology."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


SECTION = re.compile(r"^\s*\[\s*([^]]+)\s*\]")


def atomtype_lines(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    active = False
    result = []
    for line in lines:
        match = SECTION.match(line)
        if match:
            active = match.group(1).strip().lower() == "atomtypes"
            continue
        stripped = line.strip()
        if active and stripped and not stripped.startswith(";"):
            result.append(" ".join(stripped.split()))
    if not result:
        raise ValueError(f"no atom types found in {path}")
    return result


def parse_molecule_type(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    seen = False
    for line in lines:
        if SECTION.match(line) and SECTION.match(line).group(1).strip().lower() == "moleculetype":
            seen = True
            continue
        if seen:
            cleaned = line.split(";", 1)[0].strip()
            if cleaned:
                return cleaned.split()[0]
    raise ValueError(f"no molecule type found in {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cat-dir", type=Path, required=True)
    parser.add_argument("--ani-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sources = {
        "cat": (args.cat_dir.resolve() / "cat.itp", args.cat_dir.resolve() / "cat_atomtypes.itp"),
        "ani": (args.ani_dir.resolve() / "ani.itp", args.ani_dir.resolve() / "ani_atomtypes.itp"),
    }
    atomtypes: dict[str, str] = {}
    for _, (_, atomtype_file) in sources.items():
        for line in atomtype_lines(atomtype_file):
            name = line.split()[0]
            if name in atomtypes and atomtypes[name] != line:
                raise ValueError(f"conflicting GAFF2 atom type definition for {name}")
            atomtypes[name] = line
    (output / "gaff2_atomtypes.itp").write_text(
        "; De-duplicated GAFF2 atom types from independent CAT and ANI parameterizations.\n\n"
        "[ atomtypes ]\n; name at.num mass charge ptype sigma epsilon\n"
        + "\n".join(atomtypes[name] for name in sorted(atomtypes)) + "\n",
        encoding="utf-8",
    )
    molecules = {}
    for label, (itp, _) in sources.items():
        destination = output / itp.name
        shutil.copy2(itp, destination)
        molecules[label] = parse_molecule_type(itp)
    if molecules != {"cat": "CAT", "ani": "ANI"}:
        raise ValueError(f"unexpected molecule types: {molecules}")
    (output / "system.top").write_text(
        "; Noncovalent CAT/ANI ion pair in AMBER TIP3P water.\n"
        "#include \"amber14sb.ff/forcefield.itp\"\n"
        "#include \"gaff2_atomtypes.itp\"\n"
        "#include \"cat.itp\"\n"
        "#include \"ani.itp\"\n"
        "#include \"amber14sb.ff/tip3p.itp\"\n\n"
        "[ system ]\n"
        "One noncovalent CAT/ANI ion pair in excess water\n\n"
        "[ molecules ]\n"
        "CAT     1\n"
        "ANI     1\n",
        encoding="utf-8",
    )
    (output / "assembly_metadata.json").write_text(json.dumps({
        "molecule_types": molecules,
        "cross_ion_covalent_terms": 0,
        "atomtype_count": len(atomtypes),
        "system_total_charge_e": 0.0,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
