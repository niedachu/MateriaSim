"""Offline tests for bounded public-source retrieval; no network or molecular simulation."""

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studies.ethanol_water_benchmark import prepare_sources as sources


def archive_bytes(names):
    """Return tiny synthetic regular TAR members for extraction-boundary checks."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name in names:
            member = tarfile.TarInfo(name)
            member.size = 7
            archive.addfile(member, io.BytesIO(b"fixture"))
    return buffer.getvalue()


class SourceTests(unittest.TestCase):
    """Check pinning, identity, archive selection, bounded reads and non-overwrite behavior."""

    def test_pinned_blob_and_size(self):
        """Both Git identity and byte count must match before content is accepted."""
        data = b"fixture"
        blob = hashlib.sha1(b"blob 7\0" + data).hexdigest()
        sources.verify_blob(data, blob, 7)
        for value, size in [(b"changed", 7), (data, 8)]:
            with self.assertRaises(ValueError):
                sources.verify_blob(value, blob, size)

    def test_only_ethanol_members_retained(self):
        """Other molecules and traversal-like members cannot be written to disk."""
        data = archive_bytes(["../../unrelated", *sorted(sources.MEMBERS), "other.top"])
        self.assertEqual(set(sources.ethanol_members(data)), sources.MEMBERS)

    def test_missing_duplicate_and_link_members_rejected(self):
        """No symlink dereference or ambiguous repeated source can pass the exact selection."""
        names = sorted(sources.MEMBERS)
        for members in [names[:1], names + names[:1]]:
            with self.assertRaises(ValueError):
                sources.ethanol_members(archive_bytes(members))
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            member = tarfile.TarInfo(names[0])
            member.type, member.linkname = tarfile.SYMTYPE, "/not-an-input"
            archive.addfile(member)
        with self.assertRaises(ValueError):
            sources.ethanol_members(buffer.getvalue())

    def test_chemical_identity_is_not_inferred_from_filename(self):
        """The ID, SMILES and compound name must agree in the source index."""
        line = b"mobley_2310185; CCO; ethanol; -5.00\n"
        self.assertEqual(sources.ethanol_identity(line)["name"], "ethanol")
        for bad in [line.replace(b"CCO", b"COC"), line + line, b"other; CCO; ethanol\n"]:
            with self.assertRaises(ValueError):
                sources.ethanol_identity(bad)

    def test_network_read_is_bounded(self):
        """Missing Content-Length does not allow unbounded response reads."""
        response = io.BytesIO(b"123456")
        response.url, response.headers = "https://example.org/source", {}
        with patch.object(sources.urllib.request, "urlopen", return_value=response) as opened:
            with self.assertRaisesRegex(ValueError, "limit"):
                sources.retrieve(response.url, 5)
        self.assertEqual(opened.call_args.kwargs["timeout"], 20)

    def test_existing_directory_rejected_before_network(self):
        """Retries require a new output directory rather than overwriting source evidence."""
        with tempfile.TemporaryDirectory() as folder, patch.object(sources, "retrieve") as fetch:
            with self.assertRaises(FileExistsError):
                sources.prepare(folder)
            fetch.assert_not_called()

    def test_repository_output_rejected(self):
        """Downloaded reference data cannot accidentally become repository source assets."""
        with patch.object(sources, "retrieve") as fetch:
            with self.assertRaisesRegex(ValueError, "outside"):
                sources.prepare(Path(sources.__file__).parent / "downloaded")
            fetch.assert_not_called()

    def test_complete_manifest_and_exact_bytes(self):
        """A mocked acquisition exercises real saving/pinning and accounts for all retained bytes."""
        bodies = {"database.txt": b"mobley_2310185; CCO; ethanol\n",
                  "gromacs.tar.gz": archive_bytes(sorted(sources.MEMBERS))}
        files = [(name, hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest(), len(data))
                 for name, data in bodies.items()]

        def fetch(url, limit):
            """Supply synthetic upstream bytes, retaining the actual helper's limit check."""
            if url == sources.NIST:
                data = json.dumps(dict(Citation=dict(sDOI="10.1016/j.jct.2007.05.004"))).encode()
            elif url.endswith("/license"):
                data = b"Synthetic license page; not a legal source"
            else:
                data = bodies[url.rsplit("/", 1)[1]]
            self.assertLessEqual(len(data), limit)
            return data, url

        with tempfile.TemporaryDirectory() as parent, patch.object(sources, "FILES", files), patch.object(
                sources, "retrieve", side_effect=fetch):
            root = Path(parent) / "sources"
            result = sources.prepare(root)
            self.assertFalse((root / "freesolv/gromacs.tar.gz").exists())
            self.assertFalse(result["md_launched"])
            self.assertEqual(result, json.loads((root / "manifest.json").read_text()))
            self.assertEqual(result["retained_source_bytes"], sum(item["bytes"] for item in result["files"].values()))
            for name, item in result["files"].items():
                self.assertEqual(sources.digest((root / name).read_bytes()), item["sha256"])


if __name__ == "__main__":
    unittest.main()
