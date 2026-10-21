"""Hash admission and atomic persistence. No computational stage at import."""
import hashlib
import json
import os
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_manifest(root, expected_sha256):
    root = Path(root).resolve()
    raw = (root / "freeze_manifest.json").read_bytes()
    if digest(raw) != expected_sha256:
        raise RuntimeError("MANIFEST_HASH_MISMATCH")
    manifest = json.loads(raw)
    for relative, entry in manifest["files"].items():
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise RuntimeError("UNSAFE_FROZEN_PATH: " + relative)
        data = path.read_bytes()
        if digest(data) != entry["sha256"] or len(data) != entry["bytes"]:
            raise RuntimeError("FROZEN_FILE_MISMATCH: " + relative)
    return manifest


def pinned_bytes(root, manifest, relative):
    entry = manifest["files"][relative]
    path = Path(root) / relative
    if path.is_symlink() or not path.resolve().is_relative_to(Path(root).resolve()):
        raise RuntimeError("UNSAFE_FROZEN_PATH")
    data = path.read_bytes()
    if len(data) != entry["bytes"] or digest(data) != entry["sha256"]:
        raise RuntimeError("FROZEN_FILE_MISMATCH: " + relative)
    return data


def atomic_new_json(path, value):
    """Never replace an existing outcome. Caller must provide exclusive run lock.

    fsync is an OS request, NOT a promise of host/crash durability. In this
    environment fsync=volatile is an independent admission blocker.
    """
    path = Path(path)
    if path.exists():
        raise RuntimeError("REFUSE_OVERWRITE: " + str(path))
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    tmp = path.with_name(path.name + ".pending")
    with tmp.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    if path.exists():
        raise RuntimeError("REFUSE_RACE_OVERWRITE")
    os.rename(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"sha256": digest(raw), "bytes": len(raw)}


def append_event(path, event):
    """Single external supervisor owns this append-only journal."""
    raw = (json.dumps(event, sort_keys=True, allow_nan=False) + "\n").encode()
    with Path(path).open("ab") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def require_stage(manifest, stage):
    if manifest["execution"]["status"] != "ADMITTED" or stage not in manifest["execution"]["allowed_stages"]:
        raise RuntimeError("EXECUTION_BLOCKED: preparation/readback package; no T0 or worker")
