#!/usr/bin/env python3
"""Execute selected module contracts with lightweight content-addressed reuse."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.stage_3_canonical.run import run_stage as run_canonical
from modules.stage_6_items.run import run_stage as run_items
from modules.stage_5_kc.run import run_stage as run_kc
from modules.stage_9_kt.run import run_stage as run_kt
from modules.stage_2_normalization.run import run_stage as run_normalization
from modules.stage_10_provenance.run import run_stage as run_provenance
from modules.stage_7_qmatrix.run import run_stage as run_qmatrix
from modules.stage_4_realization.run import run_stage as run_realization
from modules.stage_8_simulation.run import run_stage as run_simulation
from modules.stage_1_source.run import run_stage as run_source
from shared.utils.config import resolve_experiment
from shared.utils.experiment import ensure_run_metadata
from shared.utils.io import read_json, utc_now, write_json
from shared.utils.manifests import verify_descriptor
from shared.utils.research import backup_path
from shared.utils.run_validation import validate_run
from shared.utils.stages import DEPENDENCIES, STAGES, stage_config, stage_fingerprint, transitive_requirements


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


def _selection(args: argparse.Namespace, provenance_enabled: bool) -> list[str]:
    available = list(STAGES if provenance_enabled else STAGES[:-1])
    if args.only:
        return [args.only]
    start = available.index(args.from_stage) if args.from_stage else 0
    end = available.index(args.to_stage) if args.to_stage else len(available) - 1
    if start > end:
        raise ValueError("--from must not follow --to")
    return available[start : end + 1]


def _verify_stage(stage_dir: Path) -> list[str]:
    manifest_path = stage_dir / "manifest.json"
    if not manifest_path.is_file():
        return [f"missing stage manifest: {manifest_path}"]
    try:
        manifest = read_json(manifest_path)
    except Exception as error:
        return [f"cannot read {manifest_path}: {error}"]
    errors = []
    for category in ("inputs", "configs", "code", "outputs"):
        for descriptor in manifest.get(category, []):
            problem = verify_descriptor(descriptor)
            if problem:
                errors.append(f"{manifest_path}: {problem}")
    if manifest.get("validation_status") != "PASS":
        errors.append(f"{manifest_path}: validation status is not PASS")
    return errors


def _candidate_runs(run_dir: Path, config: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    explicit = config.get("reuse", {}).get("run") if isinstance(config.get("reuse"), dict) else None
    if explicit:
        path = Path(explicit)
        candidates.append((path if path.is_absolute() else ROOT / "runs" / path).resolve())
    for candidate in sorted((ROOT / "runs").iterdir()):
        if candidate.resolve() == run_dir.resolve() or ".backup-" in candidate.name:
            continue
        if candidate.is_dir():
            candidates.append(candidate.resolve())
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def _reuse_stage(
    stage: str,
    run_dir: Path,
    fingerprint: dict[str, Any],
    candidates: list[Path],
) -> Path | None:
    destination = run_dir / stage
    if destination.exists() or destination.is_symlink():
        return None
    for candidate in candidates:
        source = candidate / stage
        manifest_path = source / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = read_json(manifest_path)
        if manifest.get("stage_fingerprint") != fingerprint["sha256"]:
            continue
        errors = _verify_stage(source)
        if errors:
            continue
        os.symlink(source.resolve(), destination, target_is_directory=True)
        return candidate
    return None


def _record_status(
    path: Path,
    statuses: dict[str, Any],
    *,
    stage: str,
    status: str,
    fingerprint: str,
    source: Path | None = None,
) -> None:
    statuses[stage] = {
        "status": status,
        "fingerprint": fingerprint,
        "from_run": str(source) if source else None,
        "recorded_utc": utc_now(),
    }
    write_json(path, {"stages": statuses})


def _stamp_executed_manifest(stage_dir: Path, fingerprint: dict[str, Any]) -> None:
    path = stage_dir / "manifest.json"
    manifest = read_json(path)
    manifest["stage_fingerprint"] = fingerprint["sha256"]
    manifest["fingerprint_basis"] = fingerprint
    manifest["execution"] = {"status": "executed", "reused_from": None}
    write_json(path, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", help="manifest path or short name under experiments/")
    parser.add_argument("--only", choices=STAGES)
    parser.add_argument("--from", dest="from_stage", choices=STAGES)
    parser.add_argument("--to", dest="to_stage", choices=STAGES)
    parser.add_argument("--force", action="store_true", help="rerun selected stages instead of reusing cache")
    parser.add_argument("--source-path", type=Path, help="override only the external EGP source path")
    args = parser.parse_args()
    if args.only and (args.from_stage or args.to_stage):
        parser.error("--only cannot be combined with --from/--to")

    resolution = resolve_experiment(args.experiment)
    if args.source_path:
        overridden = dict(resolution.resolved)
        overridden["source"] = {**overridden["source"], "path": str(args.source_path.resolve())}
        resolution = replace(resolution, resolved=overridden)
    config = resolution.resolved
    experiment_id = config.get("experiment_id")
    run_dir = ROOT / "runs" / str(experiment_id)
    summary_path = run_dir / "summary.json"
    if run_dir.exists() and summary_path.is_file() and read_json(summary_path).get("completed"):
        if not args.force:
            raise RuntimeError(f"refusing to overwrite completed run {run_dir}; use --force")
        backup = backup_path(run_dir)
        print(f"moved existing run to {backup}")
    run_dir, experiment_manifest = ensure_run_metadata(
        resolution, command=[sys.executable, *sys.argv], run_dir=run_dir
    )
    selected = _selection(args, bool(config.get("provenance", {}).get("enabled", False)))
    required = transitive_requirements(selected)
    candidates = _candidate_runs(run_dir, config)
    status_path = run_dir / "stage_status.json"
    statuses = read_json(status_path).get("stages", {}) if status_path.is_file() else {}
    command = [sys.executable, *sys.argv]

    for stage in STAGES:
        if stage not in required:
            continue
        destination = run_dir / stage
        if (destination / "manifest.json").is_file():
            if args.force and stage in selected:
                backup = backup_path(destination)
                print(f"{stage}: moved prior stage to {backup.name}")
            else:
                errors = _verify_stage(destination)
                if errors:
                    raise RuntimeError("existing stage failed manifest verification: " + "; ".join(errors[:5]))
                existing = read_json(destination / "manifest.json").get("stage_fingerprint")
                expected_fingerprint = stage_fingerprint(stage, run_dir, config)["sha256"]
                if existing != expected_fingerprint:
                    raise RuntimeError(
                        f"existing {stage} fingerprint differs from current inputs/config/implementation; use --force"
                    )
                prior = statuses.get(stage, {})
                existing_status = prior.get("status")
                if existing_status not in {"executed", "reused"}:
                    existing_status = "reused" if destination.is_symlink() else "executed"
                source = None
                if existing_status == "reused":
                    if prior.get("from_run"):
                        source = Path(prior["from_run"])
                    elif destination.is_symlink():
                        source = destination.resolve().parent
                _record_status(
                    status_path,
                    statuses,
                    stage=stage,
                    status=existing_status,
                    fingerprint=existing,
                    source=source,
                )
                continue
        elif args.force and stage in selected and (destination.exists() or destination.is_symlink()):
            backup = backup_path(destination)
            print(f"{stage}: moved prior partial stage to {backup.name}")
        for dependency in DEPENDENCIES[stage]:
            if not (run_dir / dependency / "manifest.json").is_file():
                raise RuntimeError(f"{stage} requires completed declared dependency {dependency}")
        fingerprint = stage_fingerprint(stage, run_dir, config)
        reused_from = None if (args.force and stage in selected) else _reuse_stage(
            stage, run_dir, fingerprint, candidates
        )
        if reused_from is not None:
            print(f"{stage}: reused from {reused_from.name}")
            _record_status(
                status_path, statuses, stage=stage, status="reused",
                fingerprint=fingerprint["sha256"], source=reused_from,
            )
            continue
        if stage not in selected:
            raise RuntimeError(
                f"{stage} is required by {selected} but no content-identical completed stage exists; "
                "include it in --from/--to or run the parent experiment first"
            )
        print(f"{stage}: starting", flush=True)
        RUNNERS[stage](run_dir, stage_config(stage, config), experiment_manifest, command)
        _stamp_executed_manifest(run_dir / stage, fingerprint)
        _record_status(
            status_path, statuses, stage=stage, status="executed",
            fingerprint=fingerprint["sha256"],
        )
        print(f"{stage}: complete", flush=True)

    # Materialize any other unchanged stages when possible. In particular this
    # makes `--only kt` a complete run without executing its upstream prefix.
    for stage in STAGES:
        destination = run_dir / stage
        if (destination / "manifest.json").is_file():
            continue
        if any(not (run_dir / dependency / "manifest.json").is_file() for dependency in DEPENDENCIES[stage]):
            continue
        fingerprint = stage_fingerprint(stage, run_dir, config)
        reused_from = _reuse_stage(stage, run_dir, fingerprint, candidates)
        if reused_from is not None:
            print(f"{stage}: reused unchanged result from {reused_from.name}")
            _record_status(
                status_path, statuses, stage=stage, status="reused",
                fingerprint=fingerprint["sha256"], source=reused_from,
            )

    expected = list(STAGES if config.get("provenance", {}).get("enabled", False) else STAGES[:-1])
    if all((run_dir / stage / "manifest.json").is_file() for stage in expected):
        summary = validate_run(run_dir, compare_reference=True)
        write_json(summary_path, summary)
        print(f"validation: {summary['status']} {summary['counts']}")
        if summary["status"] != "PASS":
            for error in summary["errors"][:20]:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
    else:
        write_json(
            summary_path,
            {
                "status": "PARTIAL",
                "completed": False,
                "experiment_id": experiment_id,
                "completed_stages": [stage for stage in expected if (run_dir / stage / "manifest.json").is_file()],
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
