"""Strict JSON, content identity, and single-writer Run storage."""

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    """Return a timezone-qualified UTC timestamp for operation records."""
    return datetime.now(timezone.utc).isoformat()


def unique_pairs(pairs):
    """Create a JSON object, rejecting duplicate keys instead of overwriting."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    """Reject NaN/Infinity tokens at the serialization boundary."""
    raise ValueError(f"Non-finite JSON value: {value}")


def read_json(path):
    """Read UTF-8 JSON with unique keys and finite numerical values."""
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def write_json(path, value):
    """Atomically persist JSON at path; callers own locking and overwrite policy."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256(path):
    """Hash the bytes of a regular, non-symlink file."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def content_hash(value):
    """Hash canonical JSON content independently of its disk location."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def contained(root, relative):
    """Resolve a relative artifact path without traversal or symlink escape."""
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"Unsafe artifact path: {relative}")
    root = Path(root).resolve()
    candidate = root / relative
    for part in (candidate, *candidate.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError(f"Symlink is not a frozen artifact: {part}")
    candidate.resolve().relative_to(root)
    return candidate


def inventory(root, directories):
    """Return relative file hashes under the specified Run subdirectories."""
    result = {}
    for directory in directories:
        folder = contained(root, directory)
        for path in sorted(folder.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Symlink in snapshot: {path}")
            if path.is_file():
                result[path.relative_to(root).as_posix()] = sha256(path)
    return result


def verify_hashes(root, hashes):
    """Reject absent or modified files from a persisted relative-path manifest."""
    for relative, expected in hashes.items():
        path = contained(root, relative)
        if sha256(path) != expected:
            raise ValueError(f"Frozen artifact changed: {relative}")


@contextmanager
def run_lock(root):
    """Hold a nonblocking POSIX lock; process death releases it automatically."""
    path = Path(root) / ".writer.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Run already has an active writer") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
