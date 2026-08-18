#!/usr/bin/env python3
"""Inspect one unit from an existing run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) in sys.path:
    sys.path.remove(str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "src"))

import yaml

from grammar_kt import kc, qmatrix
from grammar_kt.io import read_json, read_jsonl


def one(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any]:
    try:
        return next(row for row in rows if row.get(key) == value)
    except StopIteration as error:
        raise KeyError(f"{value} not found by {key}") from error


def inspect_normalisation(run: Path, identifier: str) -> dict[str, Any]:
    for result_path in (run / "normalisation" / "units").glob("*/result.json"):
        result = read_json(result_path)
        if result.get("input", {}).get("egp_id") == identifier or result_path.parent.name == identifier:
            phases = {}
            for phase in ("phase1", "phase2"):
                directory = result_path.parent / phase
                if not directory.is_dir():
                    continue
                selected = read_json(directory / "result.json")["selected_attempt"]
                attempt = directory / f"attempt-{selected:02d}"
                phases[phase] = {
                    "input": read_json(attempt / "input.json"),
                    "rendered_prompt": (attempt / "rendered_prompt.txt").read_text(encoding="utf-8"),
                    "invocation": read_json(attempt / "invocation.json"),
                    "raw_output": (attempt / "raw_output.txt").read_text(encoding="utf-8"),
                    "parsed_output": read_json(attempt / "parsed_output.json"),
                    "validation": read_json(attempt / "validation.json"),
                }
            return {"result": result, "phases": phases}
    raise KeyError(identifier)


def inspect_kc(run: Path, identifier: str) -> dict[str, Any]:
    opportunity = one(read_jsonl(run / "kc" / "cell_kc_projection.jsonl"), "canonical_cell_id", identifier)
    experiment = yaml.safe_load((run / "experiment.yaml").read_text(encoding="utf-8"))
    policy = kc.load_policy(kc.policy_path(experiment["kc"]["policy"]))
    return {"opportunity": opportunity, "explanation": kc.explain_policy(policy, opportunity)}


def inspect_item(run: Path, identifier: str) -> dict[str, Any]:
    candidates = read_jsonl(run / "items" / "generation" / "candidate_items.jsonl")
    item = one(candidates, "item_id", identifier)
    result = one(read_jsonl(run / "items" / "validation" / "validation_results.jsonl"), "item_id", identifier)
    generation_input = read_json(run / "items" / "generation" / "units" / identifier / "input.json")
    diagnostics = [row for row in read_jsonl(run / "items" / "validation" / "diagnostics.jsonl") if row["item_id"] == identifier]
    evidence = []
    for diagnostic in diagnostics:
        number = diagnostic["successful_attempt"]
        if number is None:
            continue
        attempt = run / "items" / "validation" / "model_units" / diagnostic["validation_unit_id"] / f"attempt-{number:02d}"
        evidence.append({
            "validation_unit_id": diagnostic["validation_unit_id"],
            "input": read_json(attempt / "input.json"),
            "rendered_prompt": (attempt / "rendered_prompt.txt").read_text(encoding="utf-8"),
            "invocation": read_json(attempt / "invocation.json"),
            "raw_output": (attempt / "raw_output.txt").read_text(encoding="utf-8"),
            "parsed_output": read_json(attempt / "parsed_output.json"),
            "validation": read_json(attempt / "validation.json"),
        })
    return {"generation_input": generation_input, "generated_item": item, "validation_result": result, "model_diagnostics": diagnostics, "model_evidence": evidence}


def inspect_kt(run: Path, identifier: str) -> dict[str, Any]:
    event = one(read_jsonl(run / "simulation" / "observable_interactions.jsonl"), "event_id", identifier)
    prediction = one(read_jsonl(run / "kt" / "predictions.jsonl"), "event_id", identifier)
    return {"observable_interaction": event, "prediction": prediction, "oracle_used_by_kt": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect one saved experimental unit.")
    parser.add_argument("kind", choices=("normalisation", "kc", "item", "qmatrix", "kt"))
    parser.add_argument("identifier")
    parser.add_argument("--run", default="base")
    args = parser.parse_args()
    run = Path(args.run)
    if not run.is_dir():
        run = ROOT / "runs" / args.run
    handlers = {
        "normalisation": inspect_normalisation,
        "kc": inspect_kc,
        "item": inspect_item,
        "qmatrix": lambda current, identifier: qmatrix.explain(current, identifier),
        "kt": inspect_kt,
    }
    print(json.dumps(handlers[args.kind](run, args.identifier), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
