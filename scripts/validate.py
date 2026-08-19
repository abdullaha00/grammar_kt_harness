#!/usr/bin/env python3
"""Validate that a saved run is complete and structurally internally consistent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Prevent this directory's inspect.py from shadowing Python's standard inspect module.
sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.io import ROOT, read_json, read_jsonl
from grammar_kt.records import grammar_cell, observable_interaction
from grammar_kt.runner import STAGE_NAMES


def validate(run: Path) -> dict:
    errors = []
    for required in ("experiment.yaml", "metadata.json"):
        if not (run / required).is_file():
            errors.append(f"missing {required}")
    for stage in STAGE_NAMES:
        if not (run / stage).is_dir():
            errors.append(f"missing stage output: {stage}")
    if (run / "canonical/canonical_cells.jsonl").is_file():
        for row in read_jsonl(run / "canonical/canonical_cells.jsonl"):
            try:
                grammar_cell(row["cell"], label=row["canonical_cell_id"])
            except ValueError as error:
                errors.append(str(error))
    for audit_file, label in (
        (run / "qmatrix" / "audit.json", "Q-matrix"),
        (run / "simulation" / "audit.json", "simulation"),
    ):
        if audit_file.is_file():
            audit = read_json(audit_file)
            if audit.get("status") != "PASS":
                errors.append(f"{label} audit failed: {audit.get('structural_errors', audit.get('errors', []))}")
    if (run / "simulation/observable_interactions.jsonl").is_file():
        for row in read_jsonl(run / "simulation/observable_interactions.jsonl"):
            try:
                observable_interaction(row, label=row.get("event_id", "interaction"))
            except ValueError as error:
                errors.append(str(error))
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "error_count": len(errors)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    args = parser.parse_args()
    run = Path(args.run)
    if not run.is_dir():
        run = ROOT / "runs" / args.run
    result = validate(run)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
