"""Run the frozen two-phase normalization contract for one descriptor."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from modules.stage_2_normalization.run import _annotate, _load_validator, _verify_frozen_artifacts
from shared.utils.config import resolve_experiment
from shared.utils.experiment import ensure_run_metadata
from shared.utils.io import read_json, read_jsonl, repo_path, write_json
from shared.utils.research import backup_path, safe_component


DEFAULT_EGP_ID = "FIX_NORM_SIMPLE"
DEFAULT_INPUT = Path(__file__).resolve().parent / "fixtures" / "core.jsonl"
DEFAULT_EXPERIMENT = "run_one_demo"


def _record_from_file(path: Path, egp_id: str) -> dict[str, Any]:
    if path.suffix == ".jsonl":
        rows = read_jsonl(path)
        try:
            return next(row for row in rows if row.get("egp_id") == egp_id)
        except StopIteration as error:
            raise KeyError(f"{egp_id} not found in {path}") from error
    value = read_json(path)
    if isinstance(value, dict) and "record" in value:
        value = value["record"]
    if not isinstance(value, dict) or value.get("egp_id") != egp_id:
        raise ValueError(f"{path} is not SourceDescriptor {egp_id}")
    return value


def _resolve_record(run_dir: Path, config: dict[str, Any], egp_id: str, explicit: Path | None) -> dict[str, Any]:
    if explicit is not None:
        return _record_from_file(explicit.resolve(), egp_id)
    run_source = run_dir / "source" / "source_subset.jsonl"
    if run_source.is_file():
        return _record_from_file(run_source, egp_id)
    return _record_from_file(repo_path(config["source"]["path"]), egp_id)


def _unit_id(config: dict[str, Any], egp_id: str) -> str:
    rows = read_jsonl(repo_path(config["source"]["annotation_units"]))
    primary = next(
        (row for row in rows if row["egp_id"] == egp_id and row["duplicate_of"] is None),
        None,
    )
    if primary is not None:
        return primary["unit_id"]
    return "one_" + hashlib.sha256(egp_id.encode("utf-8")).hexdigest()[:12]


def run_one(
    egp_id: str,
    *,
    experiment: str | Path,
    input_path: Path | None = None,
    phase1_only: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    safe_component(egp_id)
    resolution = resolve_experiment(experiment)
    config = resolution.resolved
    run_dir, _ = ensure_run_metadata(resolution)
    normalization = config["normalization"]
    _verify_frozen_artifacts(repo_path(normalization["artifact_hashes"]))
    validator = _load_validator(repo_path(normalization["validator"]))
    record = _resolve_record(run_dir, config, egp_id, input_path)
    phase1_record = {
        key: record.get(key)
        for key in ("egp_id", "supercategory", "subcategory", "guideword", "can_do")
    }
    uid = _unit_id(config, egp_id)
    unit_root = run_dir / "normalization" / "units" / uid
    if force and unit_root.exists():
        backup_path(unit_root)
    task = {"unit_id": uid, "egp_id": egp_id, "duplicate_of": None, "record": phase1_record}
    first = _annotate(
        phase=1,
        task=task,
        config=normalization,
        output=run_dir / "normalization",
        parse_raw=validator.parse_raw_mapping,
        validate_mapping=validator.validate_mapping,
        validate_transition=validator.validate_phase2_transition,
    )
    second = None
    route = first["mapping"]["result"] in {"partial", "unresolved"} and not phase1_only
    if route:
        second = _annotate(
            phase=2,
            task={
                **task,
                "phase1_mapping": first["mapping"],
                "examples": record.get("examples", []),
            },
            config=normalization,
            output=run_dir / "normalization",
            parse_raw=validator.parse_raw_mapping,
            validate_mapping=validator.validate_mapping,
            validate_transition=validator.validate_phase2_transition,
        )
    result = {
        "before": record,
        "after": (second or first)["mapping"],
        "egp_id": egp_id,
        "unit_id": uid,
        "phase1_result": first["mapping"]["result"],
        "phase2_routed": route,
        "routing_reason": (
            f"Phase 1 result {first['mapping']['result']} is routed"
            if route else (
                "--phase1-only requested" if phase1_only and first["mapping"]["result"] in {"partial", "unresolved"}
                else f"Phase 1 result {first['mapping']['result']} is terminal"
            )
        ),
        "final_mapping": (second or first)["mapping"],
        "unit_directory": str(unit_root),
    }
    write_json(unit_root / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("egp_id", nargs="?", help=f"default: {DEFAULT_EGP_ID} from the core fixture")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--phase1-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    using_default = args.egp_id is None
    result = run_one(
        args.egp_id or DEFAULT_EGP_ID,
        experiment=args.experiment,
        input_path=args.input or (DEFAULT_INPUT if using_default else None),
        phase1_only=args.phase1_only,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
