#!/usr/bin/env python3
"""Run small structural and leakage checks over a saved run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) in sys.path:
    sys.path.remove(str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt import STAGES
from grammar_kt.io import read_jsonl
from grammar_kt.models import grammar_cell, interaction
from grammar_kt.simulation import FORBIDDEN_OBSERVABLE


def validate(run: Path) -> dict:
    errors = []
    for required in ("experiment.yaml", "metadata.json"):
        if not (run / required).is_file():
            errors.append(f"missing {required}")
    for stage in STAGES:
        if not (run / stage).is_dir():
            errors.append(f"missing stage output: {stage}")
    if not (run / "qmatrix").is_dir():
        errors.append("missing derived output: qmatrix")
    if (run / "canonical/canonical_cells.jsonl").is_file():
        for row in read_jsonl(run / "canonical/canonical_cells.jsonl"):
            try:
                grammar_cell(row["cell"], label=row["canonical_cell_id"])
            except ValueError as error:
                errors.append(str(error))
    if (run / "simulation/observable_interactions.jsonl").is_file():
        for row in read_jsonl(run / "simulation/observable_interactions.jsonl"):
            leaked = FORBIDDEN_OBSERVABLE & set(row)
            if leaked:
                errors.append(f"{row.get('event_id')}: oracle/content leakage {sorted(leaked)}")
            try:
                interaction(row, label=row.get("event_id", "interaction"))
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
