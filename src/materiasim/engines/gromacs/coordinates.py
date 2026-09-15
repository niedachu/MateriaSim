"""GROMACS coordinate serialization for checked packed molecular instances."""


def write_gro(path, atoms, box):
    """Write explicit molecule residue IDs and nm coordinates using the frozen mapping order."""
    rows, molecule_ids = [], {}
    for index, atom in enumerate(atoms, 1):
        if atom["molecule_id"] not in molecule_ids:
            molecule_ids[atom["molecule_id"]] = len(molecule_ids) + 1
        x, y, z = atom["xyz_nm"]
        rows.append(f"{molecule_ids[atom['molecule_id']]:5d}{atom['resname']:<5}{atom['name']:>5}{index:5d}{x:8.3f}{y:8.3f}{z:8.3f}")
    path.write_text("Packmol engineering assembly\n" + str(len(atoms)) + "\n" + "\n".join(rows) +
                    "\n" + " ".join(str(value) for value in box) + "\n")
