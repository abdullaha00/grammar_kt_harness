#!/usr/bin/env python3
"""Run the research pipeline literally from top to bottom."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import canonicalise
from grammar_kt.evaluate import evaluate
from grammar_kt.fold import apply_fold
from grammar_kt.generate import generate_items
from grammar_kt.io import (
    load_experiment,
    load_typed_resource,
    read_yaml,
    write_json,
    write_jsonl,
    write_yaml,
)
from grammar_kt.kc import build_or_select_kcs, project_kcs, write_q_matrix
from grammar_kt.kt import run_kt
from grammar_kt.normalise import normalise
from grammar_kt.simulate import simulate
from grammar_kt.validate_items import bank_summary, validate_items


def run_pipeline(config: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Execute the complete scientific experiment in its conceptual order."""

    run_dir.mkdir(parents=True, exist_ok=False)
    write_yaml(run_dir / "resolved_experiment.yaml", config)

    resources = load_typed_resource(config["resource"]["data"], config["resource"]["schema"])

    mappings = normalise(resources, config["normalisation"], evidence_dir=run_dir / "normalisation")
    write_jsonl(run_dir / "normalisation" / "mappings.jsonl", mappings)

    cells = canonicalise(mappings, config["canonical"]["schema"])
    write_jsonl(run_dir / "canonical" / "cells.jsonl", cells)

    candidates = generate_items(cells, config["generation"], evidence_dir=run_dir / "items" / "generation")
    write_jsonl(run_dir / "items" / "candidates.jsonl", candidates)

    items, judgments = validate_items(
        candidates, cells, config["validation"], evidence_dir=run_dir / "items" / "validation_evidence"
    )
    write_jsonl(run_dir / "items" / "accepted.jsonl", items)
    write_jsonl(run_dir / "items" / "validation.jsonl", judgments)
    write_json(run_dir / "items" / "bank_summary.json", bank_summary(candidates, items, judgments, cells))

    grammar_fold = apply_fold(cells, config["fold"])
    write_jsonl(run_dir / "fold" / "assignments.jsonl", grammar_fold)

    events = simulate(
        items,
        grammar_fold,
        config["simulation"],
        oracle_path=run_dir / "simulation" / "oracle_debug.json",
    )
    write_jsonl(run_dir / "simulation" / "events.jsonl", events)

    policy = build_or_select_kcs(cells, items, grammar_fold, config["kc"])
    write_yaml(run_dir / "kc" / "frozen_policy.yaml", policy)

    projection = project_kcs(items, cells, policy)
    write_jsonl(run_dir / "kc" / "projection.jsonl", projection)
    write_q_matrix(run_dir / "kc" / "q_matrix.csv", projection)

    predictions = run_kt(events, projection, config["kt"])
    write_jsonl(run_dir / "kt" / "predictions.jsonl", predictions)

    results = evaluate(
        candidates,
        judgments,
        items,
        cells,
        grammar_fold,
        events,
        policy,
        projection,
        predictions,
        config["evaluation"],
    )
    write_json(run_dir / "evaluation" / "results.json", results)

    world = read_yaml(config["simulation"]["world"])
    kt_protocol = read_yaml(config["kt"]["protocol"])
    write_json(
        run_dir / "run_settings.json",
        {
            "seeds": {
                "simulation": world["seed"],
                "logistic": kt_protocol["logistic"]["random_seed"],
                "bootstrap": read_yaml(config["evaluation"]["protocol"])["paired_bootstrap"]["seed"],
            },
            "models": {
                stage: {
                    "model": config[stage]["model"],
                    "reasoning_effort": config[stage].get("reasoning_effort"),
                }
                for stage in ("normalisation", "generation", "validation")
            },
            "final_outputs": {
                "accepted_items": "items/accepted.jsonl",
                "events": "simulation/events.jsonl",
                "frozen_policy": "kc/frozen_policy.yaml",
                "predictions": "kt/predictions.jsonl",
                "evaluation": "evaluation/results.json",
            },
        },
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the readable grammar-to-KT pipeline.")
    parser.add_argument("experiment", nargs="?", default="base", help="experiment name or YAML path")
    parser.add_argument("--output", type=Path, help="new output directory")
    arguments = parser.parse_args()
    config = load_experiment(arguments.experiment)
    output = arguments.output or ROOT / "runs" / f"{config['experiment']}_refactored"
    results = run_pipeline(config, output)
    print(f"completed: {output}")
    print(f"accepted items: {results['dataset']['accepted_items']}")
    print(f"events: {results['input_counts']['events']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
