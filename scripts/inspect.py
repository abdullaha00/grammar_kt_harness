#!/usr/bin/env python3
"""Inspect representative artifacts by scientific module."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.io import read_json, read_jsonl


def first(path: Path) -> dict | None:
    rows = read_jsonl(path) if path.is_file() else []
    return rows[0] if rows else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument(
        "module",
        nargs="?",
        default="overview",
        choices=("overview", "grammar", "measurement", "generation", "knowledge", "evaluation"),
    )
    args = parser.parse_args()
    run = args.run.resolve()
    views = {
        "grammar": {
            "normalisation": first(run / "normalisation/final_mappings.jsonl"),
            "canonical_cell": first(run / "canonical/canonical_cells.jsonl"),
        },
        "measurement": {
            "opportunity": first(run / "measurement/measurement_opportunities.jsonl"),
            "audit": read_json(run / "measurement/audit.json") if (run / "measurement/audit.json").is_file() else None,
        },
        "generation": {
            "accepted_item": first(run / "generation/accepted_items.jsonl"),
            "validation_report": read_json(run / "generation/validation_report.json") if (run / "generation/validation_report.json").is_file() else None,
        },
        "knowledge": {
            "selected_policy": read_json(run / "knowledge_selection/selected_policy.json") if (run / "knowledge_selection/selected_policy.json").is_file() else None,
            "item_projection": first(run / "knowledge/item_kc_projection.jsonl"),
            "qmatrix_audit": read_json(run / "qmatrix/audit.json") if (run / "qmatrix/audit.json").is_file() else None,
        },
        "evaluation": {
            "simulation_audit": read_json(run / "simulation/audit.json") if (run / "simulation/audit.json").is_file() else None,
            "kt_metrics": read_json(run / "kt/metrics.json") if (run / "kt/metrics.json").is_file() else None,
        },
    }
    result = views if args.module == "overview" else views[args.module]
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
