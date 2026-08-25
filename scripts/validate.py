#!/usr/bin/env python3
"""Validate a completed five-module run at software/scientific boundaries."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.generation.items import ITEM_FIELDS, item_bank_fingerprint
from grammar_kt.grammar.schema import consistency_report
from grammar_kt.io import ROOT, read_json, read_jsonl
from grammar_kt.runner import STAGE_NAMES


def archived_imports() -> list[str]:
    errors = []
    for path in (ROOT / "src/grammar_kt").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [value.name for value in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any("archived_code" in name for name in names):
                errors.append(str(path.relative_to(ROOT)))
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    errors = []
    if consistency_report()["status"] != "PASS":
        errors.append("GrammarCell schema declarations disagree")
    for stage in STAGE_NAMES:
        if not (run / stage).is_dir():
            errors.append(f"missing stage directory: {stage}")
    opportunities = read_jsonl(run / "measurement/measurement_opportunities.jsonl") if (run / "measurement/measurement_opportunities.jsonl").is_file() else []
    items = read_jsonl(run / "generation/accepted_items.jsonl") if (run / "generation/accepted_items.jsonl").is_file() else []
    opportunity_ids = {row["measurement_opportunity_id"] for row in opportunities}
    for item in items:
        if set(item) != ITEM_FIELDS:
            errors.append(f"{item.get('item_id')}: accepted-item schema differs")
        if item.get("measurement_opportunity_id") not in opportunity_ids:
            errors.append(f"{item.get('item_id')}: unknown MeasurementOpportunity")
    validation_report = read_json(run / "generation/validation_report.json") if (run / "generation/validation_report.json").is_file() else {}
    if validation_report.get("accepted_item_bank_sha256") != item_bank_fingerprint(items):
        errors.append("accepted item-bank fingerprint differs from validation report")
    for audit_path in (run / "qmatrix/audit.json", run / "simulation/audit.json"):
        if audit_path.is_file() and read_json(audit_path).get("status") != "PASS":
            errors.append(f"failed audit: {audit_path.relative_to(run)}")
    if imports := archived_imports():
        errors.append(f"active package imports archived_code: {imports}")
    report = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "software_correctness": "checked by schemas, references, and fingerprints",
        "dataset_validity": "reported by blind reconstruction and quality diagnostics",
        "research_evidence": "requires researcher interpretation; not auto-certified",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
