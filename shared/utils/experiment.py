"""Create inspectable run metadata for both unit probes and full experiments."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import ExperimentResolution, diff_values, scientific_paths
from .io import ROOT, display_path, read_json, sha256_file, utc_now, write_json
from .manifests import describe


def git_state() -> dict[str, Any]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip())
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def ensure_run_metadata(
    resolution: ExperimentResolution,
    *,
    command: list[str] | None = None,
    run_dir: Path | None = None,
) -> tuple[Path, Path]:
    config = resolution.resolved
    experiment_id = config.get("experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id or Path(experiment_id).name != experiment_id:
        raise ValueError("experiment_id must be one safe path component")
    run_dir = run_dir or ROOT / "runs" / experiment_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "experiment_manifest.json"
    manifest = {
        "experiment_id": experiment_id,
        "resolved_config": config,
        "source_yaml": display_path(resolution.path),
        "source_yaml_sha256": sha256_file(resolution.path),
        "inheritance_chain": [
            {"path": display_path(path), "sha256": sha256_file(path)}
            for path in resolution.source_chain
        ],
        "scientific_inputs": [describe(path) for path in scientific_paths(config)],
        "harness_git": git_state(),
        "created_utc": utc_now(),
        "command": command or [sys.executable, *sys.argv],
    }
    if manifest_path.is_file():
        previous = read_json(manifest_path)
        if previous.get("resolved_config") != config:
            raise RuntimeError(f"run directory belongs to a different resolved experiment: {run_dir}")
        for field in (
            "source_yaml_sha256", "inheritance_chain", "scientific_inputs",
        ):
            if previous.get(field) != manifest[field]:
                raise RuntimeError(
                    f"declared experiment input changed after run creation ({field}): {run_dir}; "
                    "use a new experiment ID"
                )
    else:
        write_json(manifest_path, manifest)

    parent_run_manifest = None
    if resolution.parent_resolved is not None:
        parent_id = resolution.parent_resolved.get("experiment_id")
        candidate = ROOT / "runs" / str(parent_id) / "experiment_manifest.json"
        if candidate.is_file():
            parent_run_manifest = {
                "path": display_path(candidate),
                "sha256": sha256_file(candidate),
            }
    diff_path = run_dir / "diff_from_parent.json"
    all_changes = diff_values(resolution.parent_resolved or config, config)
    scientific_roots = {
        "source", "normalization", "canonical", "realization", "kc",
        "items", "qmatrix", "simulation", "kt", "provenance",
    }
    diff_record = {
        "experiment_id": experiment_id,
        "parent_experiment": (
            resolution.parent_resolved.get("experiment_id")
            if resolution.parent_resolved is not None else None
        ),
        "parent_yaml": display_path(resolution.parent_path) if resolution.parent_path else None,
        "parent_run_manifest": parent_run_manifest,
        "changed": [
            row for row in all_changes
            if row["path"].split(".", 1)[0] in scientific_roots
        ],
    }
    if diff_path.is_file() and read_json(diff_path) != diff_record:
        raise RuntimeError(f"existing parent diff disagrees with resolved experiment: {diff_path}")
    if not diff_path.exists():
        write_json(diff_path, diff_record)
    return run_dir, manifest_path
