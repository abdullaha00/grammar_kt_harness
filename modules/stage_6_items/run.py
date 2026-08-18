"""Expose generation and validation as explicit substeps under one item stage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from modules.stage_6_items.generate import run_generation
from modules.stage_6_items.validate import run_validation
from modules.stage_4_realization.engine import realize, validate_spec
from shared.utils.config import resolve_experiment
from shared.utils.io import ROOT, read_jsonl, repo_path, utc_now
from shared.utils.manifests import write_stage_manifest
from shared.utils.research import prepare_stage_directory


def evaluate_fixture(fixture: dict[str, Any], frames: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Apply the bounded deterministic item checks to one readable fixture."""

    cell, spec = fixture["cell"], fixture["spec"]
    frame = frames[spec["predicate_frame_id"]]
    errors = validate_spec(spec, cell, frame, None)
    derivation = realize(spec, cell, frame) if not errors else None
    expected_punctuation = "?" if cell["clause"].endswith("question") else "."
    if not fixture["target_answer"].endswith(expected_punctuation):
        errors.append("target punctuation does not match clause type")
    if fixture["accepted_answers"] != [fixture["target_answer"]]:
        errors.append("accepted answer set is not a deterministic singleton")
    if derivation and derivation["surface"] != fixture["target_answer"]:
        errors.append("target differs from deterministic realization")
    if frame["complement"] is not None:
        errors.append("movable complement/adjunct frame is prohibited")
    if cell["voice"] == "passive" and spec["subject"]["text"] != frame["object"]:
        errors.append("passive subject is not the frame patient")
    valid = not errors
    return {
        "fixture_label": fixture["fixture_label"],
        "valid": valid,
        "expected_valid": fixture["expected_valid"],
        "expectation_met": valid == fixture["expected_valid"],
        "errors": errors,
        "derivation": derivation,
    }


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "items"
    prepare_stage_directory(output)
    run_generation(output, run_dir, config, experiment_manifest, command)
    run_validation(output, run_dir, config, experiment_manifest, command)
    write_stage_manifest(
        output,
        module="items",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[run_dir / "kc" / "manifest.json", run_dir / "realization" / "manifest.json"],
        configs=[experiment_manifest],
        code=[Path(__file__)],
        outputs=[output / "generation", output / "validation"],
        details={"substeps": ["generation", "validation"], "substeps_separate": True},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded item-family edge fixtures.")
    parser.add_argument("--input", type=Path, default=ROOT / "modules/stage_6_items/fixtures/core.jsonl")
    parser.add_argument("--experiment", default="current")
    args = parser.parse_args()
    config = resolve_experiment(args.experiment).resolved
    frames = {
        row["predicate_frame_id"]: row
        for row in read_jsonl(repo_path(config["realization"]["lexicon"]))
    }
    results = []
    for fixture in read_jsonl(args.input.resolve()):
        results.append(evaluate_fixture(fixture, frames))
    print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(row["expectation_met"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
