"""Download only the bounded source set for candidate ethanol/water review; never launch MD."""

import argparse
import hashlib
import io
import json
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


COMMIT = "6c7d19b4b565537365ffd22006aa2cd4643200c6"
BASE = f"https://raw.githubusercontent.com/MobleyLab/FreeSolv/{COMMIT}/"
NIST = "https://trc.nist.gov/ThermoML/10.1016/j.jct.2007.05.004.json"
# Git blob identities were read from the public upstream API, not inferred from filenames.
FILES = (
    ("README.md", "0a6b4a320ebf653e5d40d8b6bffdd51acc72db82", 26421),
    ("LICENSE", "53883b1c7add1f76201c2ba4c1d1d17e5cb7ed18", 18652),
    ("LICENSE_code", "5227b6688fb5f75bf03d687c17aaf87e83c23f0f", 1057),
    ("database.txt", "6c6dbf5d27e646db5a540288ece636f9c915f363", 144897),
    ("gromacs.tar.gz", "b33ec29e4f3f4e3f259f9c2e9552945fd3857643", 831301),
)
MEMBERS = {"gromacs/mobley_2310185.gro", "gromacs/mobley_2310185.top"}


def digest(data):
    """Return SHA-256 for exact downloaded or extracted bytes."""
    return hashlib.sha256(data).hexdigest()


def verify_blob(data, blob, size):
    """Require the previously inspected Git blob identity and size before accepting a file."""
    actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if len(data) != size or actual != blob:
        raise ValueError("Upstream file differs from the pinned Git blob")


def ethanol_members(data):
    """Return exactly two regular ethanol files, never extracting arbitrary archive paths."""
    result = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r|gz") as archive:
        for item in archive:
            if item.name not in MEMBERS:
                continue
            if item.name in result or not item.isfile() or not 0 < item.size <= 100_000:
                raise ValueError("Invalid or duplicate ethanol archive member")
            result[item.name] = archive.extractfile(item).read()
    if set(result) != MEMBERS:
        raise ValueError("Missing pinned ethanol coordinate/topology members")
    return result


def ethanol_identity(data):
    """Check that the requested FreeSolv ID denotes ethanol with SMILES CCO."""
    rows = [line.split(";") for line in data.decode().splitlines()
            if line.strip() and not line.startswith("#")]
    selected = [row for row in rows if row[0].strip() == "mobley_2310185"]
    if len(selected) != 1 or [value.strip() for value in selected[0][1:3]] != ["CCO", "ethanol"]:
        raise ValueError("FreeSolv ethanol identity mismatch")
    return {"id": "mobley_2310185", "smiles": "CCO", "name": "ethanol"}


def retrieve(url, limit):
    """Read at most limit bytes over HTTPS with a 20-second socket timeout; do not execute content."""
    request = urllib.request.Request(url, headers={"User-Agent": "MateriaSim research data review"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if not response.url.startswith("https://"):
            raise ValueError("Unexpected non-HTTPS redirect")
        length = response.headers.get("Content-Length")
        if length is not None and int(length) > limit:
            raise ValueError("Source exceeds the download size limit")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Source exceeds the download size limit")
        return data, response.url


def prepare(output):
    """Write a fresh external source folder and manifest; stop on failure, never overwrite or simulate."""
    output = Path(output).resolve()
    project = Path(__file__).resolve().parents[2]
    if output == project or project in output.parents:
        raise ValueError("Downloaded review sources must stay outside the repository")
    output.mkdir(parents=True, exist_ok=False)
    records, files, total = [], {}, 0

    def save(relative, data):
        """Preserve exact bytes under a fixed local name and record their content hash."""
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
        files[relative] = dict(bytes=len(data), sha256=digest(data))

    for name, blob, size in FILES:
        data, final_url = retrieve(BASE + name, size)
        verify_blob(data, blob, size)
        total += len(data)
        record = dict(url=BASE + name, resolved_url=final_url, bytes=len(data), sha256=digest(data), git_blob=blob)
        if name.endswith(".tar.gz"):
            record["retained_archive"] = False
            record["extracted_members"] = sorted(MEMBERS)
            for member, content in ethanol_members(data).items():
                save("freesolv/" + Path(member).name, content)
        else:
            if name == "database.txt":
                identity = ethanol_identity(data)
            save("freesolv/" + name, data)
        records.append(record)
    for url, name, limit in (
        (NIST, "nist/j.jct.2007.05.004.json", 500_000),
        ("https://www.nist.gov/open/license", "nist/license.html", 300_000),
    ):
        data, final_url = retrieve(url, limit)
        if name.endswith(".json"):
            if json.loads(data)["Citation"]["sDOI"] != "10.1016/j.jct.2007.05.004":
                raise ValueError("NIST citation mismatch")
        total += len(data)
        save(name, data)
        records.append(dict(url=url, resolved_url=final_url, bytes=len(data), sha256=digest(data)))
    result = dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
                  status="sources_acquired_not_model_validated", freesolv_commit=COMMIT,
                  ethanol=identity, transfers=records, files=files, download_bytes=total,
                  retained_source_bytes=sum(item["bytes"] for item in files.values()),
                  md_launched=False, dependencies_installed=False,
                  limitations=["Candidate GAFF parameters; no mixed-liquid applicability approval.",
                               "NIST dataset not yet cross-checked against full article/SI.",
                               "No new catalog model, accepted review or simulation protocol."])
    with (output / "manifest.json").open("x") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return result


def main():
    """Require explicit external storage; importing the module never performs network access."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = prepare(args.output)
    print(json.dumps({key: result[key] for key in
                      ("status", "download_bytes", "retained_source_bytes", "md_launched")}, indent=2))


if __name__ == "__main__":
    main()
