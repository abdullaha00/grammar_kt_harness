"""Tiny helpers shared by human-facing run-one/inspect commands."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from .io import ROOT


def resolve_run(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() and len(path.parts) == 1:
        path = ROOT / "runs" / path
    if not path.exists():
        raise FileNotFoundError(f"run not found: {path}")
    return path.resolve()


def safe_component(value: str) -> str:
    if not value or Path(value).name != value or value in {".", ".."}:
        raise ValueError(f"unsafe unit identifier: {value!r}")
    return value


def backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = path.with_name(f"{path.name}.backup-{stamp}")
    serial = 1
    while candidate.exists() or candidate.is_symlink():
        serial += 1
        candidate = path.with_name(f"{path.name}.backup-{stamp}-{serial}")
    shutil.move(str(path), str(candidate))
    return candidate


def prepare_unit_directory(path: Path, *, force: bool = False) -> Path:
    if path.exists() or path.is_symlink():
        if not force:
            raise RuntimeError(f"refusing to overwrite unit evidence: {path}; use --force")
        backup_path(path)
    path.mkdir(parents=True)
    return path


def prepare_stage_directory(path: Path) -> None:
    """Permit run-one evidence to precede a batch stage, but nothing else."""

    if not path.exists():
        path.mkdir(parents=True)
        return
    unexpected = [entry for entry in path.iterdir() if entry.name != "units"]
    if unexpected:
        raise RuntimeError(f"refusing to overwrite existing stage output: {path}")
