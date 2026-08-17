"""Compact stage manifests: file hashes, directory tree hashes, and commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .io import ROOT, display_path, sha256_file, tree_sha256, utc_now, write_json


def describe(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_file():
        return {
            "path": display_path(path),
            "kind": "file",
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    digest, count = tree_sha256(path)
    return {"path": display_path(path), "kind": "directory", "sha256": digest, "files": count}


def write_stage_manifest(
    stage_dir: Path,
    *,
    module: str,
    version: str,
    started_utc: str,
    command: list[str],
    inputs: Iterable[Path],
    configs: Iterable[Path],
    code: Iterable[Path],
    outputs: Iterable[Path],
    details: dict[str, Any] | None = None,
    status: str = "PASS",
) -> Path:
    manifest = {
        "module": module,
        "version": version,
        "started_utc": started_utc,
        "finished_utc": utc_now(),
        "command": command,
        "inputs": [describe(path) for path in inputs],
        "configs": [describe(path) for path in configs],
        "code": [describe(path) for path in code],
        "outputs": [describe(path) for path in outputs],
        "validation_status": status,
        "details": details or {},
    }
    target = stage_dir / "manifest.json"
    write_json(target, manifest)
    return target


def resolve_record_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def verify_descriptor(record: dict[str, Any]) -> str | None:
    path = resolve_record_path(record["path"])
    if not path.exists():
        return f"missing manifest path: {record['path']}"
    if record["kind"] == "file":
        actual = sha256_file(path)
    elif record["kind"] == "directory":
        actual, _ = tree_sha256(path)
    else:
        return f"unknown manifest path kind: {record.get('kind')}"
    if actual != record["sha256"]:
        return f"hash mismatch: {record['path']}"
    return None

