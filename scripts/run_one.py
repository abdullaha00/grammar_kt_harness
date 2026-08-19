#!/usr/bin/env python3
"""Run one scientific component from a fixture or explicit input file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt import canonical, items, kc, normalisation, realisation, simulation, source
from grammar_kt.config import resolve_experiment
from grammar_kt.io import ROOT, read_json, read_jsonl, write_json


def fixture(stage: str, name: str | None) -> dict[str, Any]:
    if stage == "canonical":
        realisation_fixture = read_jsonl(ROOT / "modules" / "realisation" / "fixtures" / "core.jsonl")[0]
        return {
            "egp_id": name or "FIX_CANONICAL",
            "result": "complete",
            "cells": [realisation_fixture["cell"]],
            "note": None,
        }

    directory = ROOT / "modules" / stage / "fixtures"
    rows: list[dict[str, Any]] = []
    for filename in sorted(directory.glob("*")):
        if filename.suffix == ".jsonl":
            rows.extend(read_jsonl(filename))
        elif filename.suffix == ".json":
            rows.append(read_json(filename))
    if not rows:
        raise FileNotFoundError(f"no {stage} fixtures")
    if name is None:
        return rows[0]
    for row in rows:
        labels = {
            str(row.get("fixture_label", "")),
            str(row.get("egp_id", "")),
            str(row.get("canonical_cell_id", "")),
            str(row.get("opportunity_id", "")),
            str(row.get("item_id", "")),
        }
        if name in labels:
            return row
    available = [row.get("fixture_label") for row in rows]
    raise KeyError(f"fixture {name!r} not found; available: {available}")


def resolve_input(args: argparse.Namespace, settings: dict[str, Any]) -> dict[str, Any]:
    if args.input:
        return read_json(args.input)
    if args.egp_id:
        if args.stage not in {"source", "normalisation"}:
            raise ValueError("--egp-id is only valid for source or normalisation")
        selected, _metadata, _units = source.select(settings["source"])
        try:
            return next(row for row in selected if row["egp_id"] == args.egp_id)
        except StopIteration as error:
            raise KeyError(f"selected EGP descriptor not found: {args.egp_id}") from error
    return fixture(args.stage, args.fixture or None)


def execute(args: argparse.Namespace) -> tuple[Any, Any]:
    settings = resolve_experiment(args.experiment).settings
    if args.stage == "simulation":
        learner_id = args.learner or "L0001"
        before = {
            "learner_id": learner_id,
            "settings": settings["simulation"],
            "fixture": "modules/simulation/fixtures",
        }
        return before, simulation.run_one(learner_id, settings["simulation"])

    before = resolve_input(args, settings)
    if args.stage == "source":
        after = source.phase1_record(before)
    elif args.stage == "normalisation":
        after = normalisation.normalise_one(
            before,
            settings["normalisation"],
            output=args.output,
            phase1_only=args.phase1_only,
        )
    elif args.stage == "canonical":
        mapping = before.get("output", before)
        cells, edges = canonical.build([mapping])
        after = {"cells": cells, "edges": edges}
    elif args.stage == "realisation":
        if "derivation" in before:
            before = {
                "spec": before["spec"],
                "cell": before["cell"],
                "source_note": before.get("source_note"),
                "expected_surface": before["derivation"]["surface"],
            }
        after = realisation.run_one(before)
    elif args.stage == "kc":
        after = kc.run_one(before, args.policy or settings["kc"]["policy"])
    elif args.stage == "items":
        after = items.evaluate_fixture(before)
    else:
        raise ValueError(f"run-one is not defined for {args.stage}")
    return before, after


def main() -> int:
    parser = argparse.ArgumentParser(description="Show one component's input and output.")
    parser.add_argument(
        "stage",
        choices=("source", "normalisation", "canonical", "realisation", "kc", "items", "simulation"),
    )
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--fixture", nargs="?", const="", help="fixture label; omit the label for the default")
    inputs.add_argument("--input", type=Path, help="explicit one-record JSON file")
    inputs.add_argument("--egp-id", help="selected external EGP descriptor ID")
    parser.add_argument("--experiment", default="base")
    parser.add_argument("--policy", help="KC policy path or short name")
    parser.add_argument("--learner", help="simulation fixture learner ID")
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
