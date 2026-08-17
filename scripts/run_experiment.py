#!/usr/bin/env python3
"""Connect module contracts in dependency order; scientific logic stays in modules."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.canonical.run import run_stage as run_canonical
from modules.items.run import run_stage as run_items
from modules.kc.run import run_stage as run_kc
from modules.kt.run import run_stage as run_kt
from modules.normalization.run import run_stage as run_normalization
from modules.provenance.run import run_stage as run_provenance
from modules.qmatrix.run import run_stage as run_qmatrix
from modules.realization.run import run_stage as run_realization
from modules.simulation.run import run_stage as run_simulation
from modules.source.run import run_stage as run_source
from shared.utils.config import load_experiment
from shared.utils.io import display_path, read_json, repo_path, sha256_file, utc_now, write_json
from shared.utils.run_validation import STAGES, validate_run, verify_manifests


StageRunner = Callable[[Path, dict[str, Any], Path, list[str]], None]
RUNNERS: dict[str, StageRunner] = {
    "source": run_source,
    "normalization": run_normalization,
    "canonical": run_canonical,
    "realization": run_realization,
    "kc": run_kc,
    "items": run_items,
    "qmatrix": run_qmatrix,
    "simulation": run_simulation,
    "kt": run_kt,
    "provenance": run_provenance,
}


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _backup(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = path.with_name(f"{path.name}.backup-{stamp}")
    serial = 1
    while candidate.exists() or candidate.is_symlink():
        serial += 1
        candidate = path.with_name(f"{path.name}.backup-{stamp}-{serial}")
    shutil.move(str(path), str(candidate))
    return candidate


def _stage_config(stage: str, config: dict[str, Any]) -> dict[str, Any]:
    value = dict(config[stage])
    if stage == "items":
        value["_realization"] = config["realization"]
    elif stage == "qmatrix":
        value["_realization"] = config["realization"]
        value["_kc"] = config["kc"]
    return value


def _reuse(run_dir: Path, config: dict[str, Any], manifest_path: Path) -> set[str]:
    reuse = config.get("reuse")
    if not reuse:
        return set()
    base_value = reuse.get("run")
    through = reuse.get("through")
    if not isinstance(base_value, str) or through not in STAGES:
        raise ValueError("reuse requires 'run' and a valid 'through' stage")
    base = Path(base_value)
    if not base.is_absolute():
        base = ROOT / "runs" / base
    base = base.resolve()
    errors = verify_manifests(base)
    if errors:
        raise RuntimeError("cannot reuse a run with invalid manifests: " + "; ".join(errors[:5]))
    base_manifest_path = base / "experiment_manifest.json"
    if not base_manifest_path.is_file():
        raise RuntimeError(f"reuse base has no experiment manifest: {base}")
    base_record = read_json(base_manifest_path)
    base_config = base_record.get("resolved_config", base_record)
    reusable = set(STAGES[: STAGES.index(through) + 1])
    for stage in reusable:
        if stage == "provenance" and not config.get("provenance", {}).get("enabled", False):
            continue
        if config.get(stage) != base_config.get(stage):
            raise RuntimeError(f"cannot reuse through {through}: {stage} configuration differs")
        source = base / stage
        destination = run_dir / stage
        if not (source / "manifest.json").is_file():
            raise RuntimeError(f"reuse base is missing completed stage {stage}: {source}")
        if destination.exists() or destination.is_symlink():
            raise RuntimeError(f"reuse target already exists: {destination}")
        os.symlink(source, destination, target_is_directory=True)
    write_json(
        run_dir / "reuse.json",
        {
            "base_run": str(base),
            "through": through,
            "stages": sorted(reusable, key=STAGES.index),
            "base_experiment_manifest": display_path(base_manifest_path),
            "base_experiment_manifest_sha256": sha256_file(base_manifest_path),
            "new_experiment_manifest": display_path(manifest_path),
        },
    )
    return reusable


def _selection(args: argparse.Namespace, provenance_enabled: bool) -> list[str]:
    available = list(STAGES if provenance_enabled else STAGES[:-1])
    if args.only:
        return [args.only]
    start = available.index(args.from_stage) if args.from_stage else 0
    end = available.index(args.to_stage) if args.to_stage else len(available) - 1
    if start > end:
        raise ValueError("--from must not follow --to")
    return available[start : end + 1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", type=Path)
    controls = parser.add_mutually_exclusive_group()
    controls.add_argument("--only", choices=STAGES)
    parser.add_argument("--from", dest="from_stage", choices=STAGES)
    parser.add_argument("--to", dest="to_stage", choices=STAGES)
    parser.add_argument("--force", action="store_true", help="move an existing run aside before starting again")
    parser.add_argument("--source-path", type=Path, help="override only the external EGP source path")
    args = parser.parse_args()
    if args.only and (args.from_stage or args.to_stage):
        parser.error("--only cannot be combined with --from/--to")
    experiment_path = args.experiment.resolve()
    config = load_experiment(experiment_path)
    experiment_id = config.get("experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id or Path(experiment_id).name != experiment_id:
        raise ValueError("experiment_id must be one safe path component")
    if args.source_path:
        config["source"] = {**config["source"], "path": str(args.source_path.resolve())}
    run_dir = ROOT / "runs" / experiment_id
    if run_dir.exists() or run_dir.is_symlink():
        if args.force:
            backup = _backup(run_dir)
            print(f"moved existing run to {backup}")
        else:
            summary_path = run_dir / "summary.json"
            if summary_path.is_file() and read_json(summary_path).get("completed"):
                raise RuntimeError(f"refusing to overwrite completed run {run_dir}; use --force")
    run_dir.mkdir(parents=True, exist_ok=True)
    experiment_manifest = run_dir / "experiment_manifest.json"
    record = {
        "experiment_id": experiment_id,
        "resolved_config": config,
        "source_yaml": str(experiment_path),
        "source_yaml_sha256": sha256_file(experiment_path),
        "harness_git_commit": _git_commit(),
        "created_utc": utc_now(),
        "command": [sys.executable, *sys.argv],
    }
    if experiment_manifest.is_file():
        previous = read_json(experiment_manifest)
        comparable = {key: value for key, value in previous.items() if key != "command"}
        current = {key: value for key, value in record.items() if key != "command"}
        # Timestamps differ on resumption; every scientific/config field must not.
        comparable.pop("created_utc", None)
        current.pop("created_utc", None)
        if comparable != current:
            raise RuntimeError(f"existing partial run was created from a different resolved experiment: {run_dir}")
    else:
        write_json(experiment_manifest, record)

    if any(run_dir.rglob("manifest.json")):
        manifest_errors = verify_manifests(run_dir)
        if manifest_errors:
            raise RuntimeError("existing upstream manifest/hash check failed: " + "; ".join(manifest_errors[:5]))
    reused = _reuse(run_dir, config, experiment_manifest)
    selected = _selection(args, bool(config.get("provenance", {}).get("enabled", False)))
    command = [sys.executable, *sys.argv]
    for stage in selected:
        if stage in reused:
            print(f"{stage}: reused from immutable base run")
            continue
        destination = run_dir / stage
        if destination.exists() or destination.is_symlink():
            raise RuntimeError(f"refusing to overwrite existing stage {stage}: {destination}")
        for upstream in STAGES[: STAGES.index(stage)]:
            if upstream == "kt" and stage == "provenance":
                # Provenance does not consume KT output.
                continue
            if not (run_dir / upstream / "manifest.json").is_file():
                raise RuntimeError(f"{stage} requires completed upstream stage {upstream}")
        print(f"{stage}: starting", flush=True)
        RUNNERS[stage](run_dir, _stage_config(stage, config), experiment_manifest, command)
        print(f"{stage}: complete", flush=True)

    required_stages = list(STAGES if config.get("provenance", {}).get("enabled", False) else STAGES[:-1])
    if all((run_dir / stage / "manifest.json").is_file() for stage in required_stages):
        summary = validate_run(run_dir, compare_reference=True)
        write_json(run_dir / "summary.json", summary)
        print(f"validation: {summary['status']} {summary['counts']}")
        if summary["status"] != "PASS":
            for error in summary["errors"][:20]:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
    else:
        write_json(
            run_dir / "summary.json",
            {
                "status": "PARTIAL",
                "completed": False,
                "experiment_id": experiment_id,
                "completed_stages": [stage for stage in required_stages if (run_dir / stage / "manifest.json").is_file()],
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
