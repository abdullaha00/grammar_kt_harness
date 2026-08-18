#!/usr/bin/env python3
"""Run one scientific component on one readable example."""

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

from grammar_kt import canonical, items, kc, normalisation, realisation, simulation, source
from grammar_kt.config import resolve_experiment
from grammar_kt.io import read_json, read_jsonl, resource, write_json
from grammar_kt.runner import prepared_config


def fixture(module: str, name: str | None) -> dict[str, Any]:
    if module == "canonical":
        realisation_fixture = read_jsonl(ROOT / "modules/realisation/fixtures/core.jsonl")[0]
        return {
            "egp_id": name or "FIX_CANONICAL",
            "result": "complete",
            "cells": [realisation_fixture["cell"]],
            "note": None,
        }
    directory = ROOT / "modules" / module / "fixtures"
    rows: list[dict[str, Any]] = []
    for filename in sorted(directory.glob("*")):
        if filename.suffix == ".jsonl":
            rows.extend(read_jsonl(filename))
        elif filename.suffix == ".json":
            rows.append(read_json(filename))
    if not rows:
        raise FileNotFoundError(f"no {module} fixtures")
    if name is None:
        return rows[0]
    for row in rows:
        labels = {str(row.get("fixture_label", "")), str(row.get("egp_id", "")), str(row.get("canonical_cell_id", "")), str(row.get("opportunity_id", "")), str(row.get("item_id", ""))}
        if name in labels:
            return row
    raise KeyError(f"fixture {name!r} not found; available: {[row.get('fixture_label') for row in rows]}")


def from_run(stage: str, identifier: str, experiment: str) -> dict[str, Any] | None:
    run = ROOT / "runs" / experiment
    choices = {
        "normalisation": run / "source" / "source_subset.jsonl",
        "realisation": run / "realisation" / "realisations.jsonl",
        "kc": run / "kc" / "cell_kc_projection.jsonl",
        "items": run / "items" / "generation" / "candidate_items.jsonl",
    }
    filename = choices.get(stage)
    if not filename or not filename.is_file():
        return None
    for row in read_jsonl(filename):
        values = {
            row.get("egp_id"), row.get("canonical_cell_id"), row.get("opportunity_id"),
            row.get("item_id"), row.get("provenance", {}).get("opportunity_id"),
        }
        if stage == "realisation":
            values.add(row.get("spec", {}).get("canonical_cell_id"))
        if identifier in values:
            if stage == "items":
                projection = next(
                    item for item in read_jsonl(run / "kc" / "cell_kc_projection.jsonl")
                    if item["canonical_cell_id"] == row["canonical_cell_id"]
                )
                return {
                    "fixture_label": f"saved item {row['item_id']}",
                    "cell": projection["cell"],
                    "spec": row["realization_spec"],
                    "target_answer": row["target_answer"],
                    "accepted_answers": row["accepted_answers"],
                    "expected_valid": True,
                    "saved_item": row,
                }
            return row
    return None


def resolve_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.input:
        return read_json(args.input)
    if args.fixture is not None:
        return fixture(args.stage, args.fixture or None)
    if args.identifier:
        found = from_run(args.stage, args.identifier, args.experiment)
        if found:
            return found
        try:
            return fixture(args.stage, args.identifier)
        except (KeyError, FileNotFoundError):
            if args.stage == "normalisation":
                config = prepared_config(resolve_experiment(args.experiment))["source"]
                for row in read_jsonl(config["path"]):
                    if row.get("egp_id") == args.identifier:
                        return row
            raise
    return fixture(args.stage, None)


def execute(args: argparse.Namespace) -> tuple[Any, Any]:
    config = prepared_config(resolve_experiment(args.experiment))
    if args.stage == "simulation":
        learner_id = args.identifier or "L0001"
        before = {"learner_id": learner_id, "config": config["simulation"], "fixture": "modules/simulation/fixtures"}
        return before, simulation.run_one(learner_id, config["simulation"])
    before = resolve_input(args)
    if args.stage == "source":
        after = source.run_one(before)
    elif args.stage == "normalisation":
        after = normalisation.normalise_one(before, config["normalisation"], output=args.output, phase1_only=args.phase1_only)
    elif args.stage == "canonical":
        mapping = before.get("output", before)
        after = {"cells": canonical.build([mapping])[0], "edges": canonical.build([mapping])[1]}
    elif args.stage == "realisation":
        if "derivation" in before:
            before = {"spec": before["spec"], "cell": before["cell"], "source_note": before.get("source_note"), "expected_surface": before["derivation"]["surface"]}
        after = realisation.run_one(before, config["realisation"])
    elif args.stage == "kc":
        after = kc.run_one(before, args.policy or config["kc"]["policy"])
    elif args.stage == "items":
        after = items.evaluate_fixture(before, config["items"])
    else:
        raise ValueError(f"run-one is not defined for {args.stage}")
    return before, after


def main() -> int:
    parser = argparse.ArgumentParser(description="Show one component's input and output.")
    parser.add_argument("stage", choices=("source", "normalisation", "canonical", "realisation", "kc", "items", "simulation"))
    parser.add_argument("identifier", nargs="?")
    parser.add_argument("--experiment", default="base")
    parser.add_argument("--fixture", nargs="?", const="", help="fixture label; omit label for the default")
    parser.add_argument("--input", type=Path, help="explicit one-record JSON file")
    parser.add_argument("--policy", help="KC policy filename or short name")
    parser.add_argument("--phase1-only", action="store_true")
    parser.add_argument("--output", type=Path, help="directory for model evidence/debug output")
    args = parser.parse_args()
    before, after = execute(args)
    print("=== BEFORE ===")
    print(json.dumps(before, ensure_ascii=False, indent=2, sort_keys=True))
    print("=== AFTER ===")
    print(json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True))
    if args.output and args.stage != "normalisation":
        write_json(args.output / "result.json", {"before": before, "after": after})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
