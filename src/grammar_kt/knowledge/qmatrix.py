"""Mechanically convert a frozen item–KC projection into a Q-matrix."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

from ..io import read_jsonl, write_json, write_jsonl


LOW_SUPPORT_ITEM_COUNT = 5


def _rule_scope(expression: dict[str, Any]) -> str:
    if any(field in expression for field in ("operation", "agreement_site", "predicate_class")):
        return "measurement"
    nested = expression.get("all", []) + expression.get("any", [])
    return "measurement" if any(_rule_scope(part) == "measurement" for part in nested) else "cell"


def build(
    items: list[dict[str, Any]], cards: list[dict[str, Any]], projections: list[dict[str, Any]],
) -> tuple[list[str], list[tuple[str, list[int]]], list[dict[str, Any]], dict[str, Any]]:
    errors: list[str] = []
    item_ids = [row["item_id"] for row in items]
    projection_ids = [row["item_id"] for row in projections]
    if len(item_ids) != len(set(item_ids)):
        errors.append("accepted item IDs are duplicated")
    if len(projection_ids) != len(set(projection_ids)):
        errors.append("frozen projection item IDs are duplicated")
    if set(item_ids) != set(projection_ids):
        errors.append(
            "projection does not exactly cover accepted items: "
            f"missing={sorted(set(item_ids) - set(projection_ids))}, "
            f"unknown={sorted(set(projection_ids) - set(item_ids))}"
        )
    by_projection = {row["item_id"]: row for row in projections}
    by_card = {row["kc_id"]: row for row in cards}
    kc_ids = sorted(by_card)
    rows: list[tuple[str, list[int]]] = []
    edges: list[dict[str, Any]] = []
    uncovered: list[str] = []
    for item in sorted(items, key=lambda row: row["item_id"]):
        projection = by_projection.get(item["item_id"])
        expected = projection["kc_ids"] if projection else []
        if projection:
            for field in ("measurement_opportunity_id", "canonical_cell_id"):
                if projection[field] != item[field]:
                    errors.append(f"{item['item_id']}: projected {field} differs")
        unknown = sorted(set(expected) - set(kc_ids))
        if unknown:
            errors.append(f"{item['item_id']}: unknown KCs {unknown}")
        if not expected:
            uncovered.append(item["item_id"])
        values = [int(kc_id in expected) for kc_id in kc_ids]
        rows.append((item["item_id"], values))
        for kc_id in expected:
            if kc_id not in by_card:
                continue
            rule = by_card[kc_id]["activation_rule"]
            edges.append(
                {
                    "item_id": item["item_id"],
                    "measurement_opportunity_id": item["measurement_opportunity_id"],
                    "canonical_cell_id": item["canonical_cell_id"],
                    "kc_id": kc_id,
                    "activation_scope": _rule_scope(rule),
                    "activation_rule": rule,
                }
            )
    columns = {kc_id: tuple(values[index] for _item_id, values in rows) for index, kc_id in enumerate(kc_ids)}
    identical = [
        [left, right]
        for index, left in enumerate(kc_ids)
        for right in kc_ids[index + 1 :]
        if columns[left] == columns[right]
    ]
    row_widths = [sum(values) for _item_id, values in rows]
    support = {kc_id: sum(columns[kc_id]) for kc_id in kc_ids}
    diagnostics = {
        "density": len(edges) / (len(items) * len(kc_ids)) if items and kc_ids else 0.0,
        "uncovered_item_ids": uncovered,
        "identical_q_columns": identical,
        "row_width_distribution": dict(sorted(Counter(row_widths).items())),
        "max_row_width": max(row_widths, default=0),
        "kc_item_support": support,
        "low_support_threshold": LOW_SUPPORT_ITEM_COUNT,
        "low_support_kcs": {kc_id: count for kc_id, count in support.items() if count < LOW_SUPPORT_ITEM_COUNT},
    }
    audit = {
        "status": "PASS" if not errors else "FAIL",
        "structural_errors": errors,
        "items": len(items),
        "covered_items": len(items) - len(uncovered),
        "uncovered_items": len(uncovered),
        "kcs": len(kc_ids),
        "one_entries": len(edges),
        "projection_unit": "accepted_item_via_measurement_opportunity",
        "scientific_diagnostics": diagnostics,
    }
    return kc_ids, rows, edges, audit


def run(run_dir: Path, _settings: dict[str, Any] | None = None) -> dict[str, Any]:
    items = read_jsonl(run_dir / "generation" / "accepted_items.jsonl")
    projections = read_jsonl(run_dir / "knowledge" / "item_kc_projection.jsonl")
    cards = read_jsonl(run_dir / "knowledge" / "projected_kc_inventory.jsonl")
    kc_ids, rows, edges, audit = build(items, cards, projections)
    if audit["status"] != "PASS":
        raise RuntimeError("Q-matrix validation failed: " + "; ".join(audit["structural_errors"]))
    output = run_dir / "qmatrix"
    output.mkdir(parents=True, exist_ok=False)
    with (output / "q_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["item_id", *kc_ids])
        for item_id, values in rows:
            writer.writerow([item_id, *values])
    write_jsonl(output / "item_kc_edges.jsonl", edges, sort_keys=False)
    write_json(output / "audit.json", audit)
    return {"rows": len(rows), "columns": len(kc_ids), "edges": len(edges)}
