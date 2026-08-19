"""Derive item-KC edges from accepted items and the frozen KC projection."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

from .io import read_jsonl, write_json, write_jsonl


LOW_SUPPORT_ITEM_COUNT = 5


def build(
    items: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    projections: list[dict[str, Any]],
) -> tuple[list[str], list[tuple[str, list[int]]], list[dict[str, Any]], dict[str, Any]]:
    """Build Q records, separating integrity failures from scientific diagnostics."""

    structural_errors: list[str] = []
    item_ids = [row["item_id"] for row in items]
    kc_ids = sorted(row["kc_id"] for row in cards)
    cell_ids = [row["canonical_cell_id"] for row in projections]
    if not items:
        structural_errors.append("no accepted items")
    if not cards:
        structural_errors.append("no KC inventory")
    if not projections:
        structural_errors.append("no canonical-cell projections")
    if len(item_ids) != len(set(item_ids)):
        structural_errors.append("duplicate item IDs")
    if len(kc_ids) != len(set(kc_ids)):
        structural_errors.append("duplicate KC IDs")
    if len(cell_ids) != len(set(cell_ids)):
        structural_errors.append("duplicate canonical-cell projections")

    projection_by_cell = {row["canonical_cell_id"]: row for row in projections}
    card_by_id = {row["kc_id"]: row for row in cards}
    known_kcs = set(card_by_id)
    rows: list[tuple[str, list[int]]] = []
    edges: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda row: row["item_id"]):
        projection = projection_by_cell.get(item["canonical_cell_id"])
        if projection is None:
            structural_errors.append(f"{item['item_id']}: unknown canonical cell")
            expected: list[str] = []
        else:
            expected = projection["kc_ids"]
        unknown = sorted(set(expected) - known_kcs)
        if unknown:
            structural_errors.append(f"{item['item_id']}: projection contains unknown KCs {unknown}")
        if item["all_kc_ids"] != expected:
            structural_errors.append(f"{item['item_id']}: stored KC list differs from frozen projection")
        if not expected:
            structural_errors.append(f"{item['item_id']}: item has no active KC")

        values = [int(kc_id in expected) for kc_id in kc_ids]
        rows.append((item["item_id"], values))
        for kc_id in expected:
            if kc_id not in card_by_id:
                continue
            edges.append(
                {
                    "item_id": item["item_id"],
                    "kc_id": kc_id,
                    "canonical_cell_id": item["canonical_cell_id"],
                    "realization_id": item["realization_spec"]["realization_id"],
                    "source_descriptor_ids": item["source_descriptor_ids"],
                    "activation_rule": card_by_id[kc_id]["activation_rule"],
                }
            )

    columns = {
        kc_id: tuple(values[index] for _item_id, values in rows)
        for index, kc_id in enumerate(kc_ids)
    }
    identical_columns = [
        [left, right]
        for index, left in enumerate(kc_ids)
        for right in kc_ids[index + 1 :]
        if columns[left] == columns[right]
    ]
    row_sums = [sum(values) for _item_id, values in rows]
    wide_rows = [item_id for item_id, values in rows if sum(values) > 4]
    kc_support = {kc_id: sum(columns[kc_id]) for kc_id in kc_ids}
    low_support = {
        kc_id: count for kc_id, count in kc_support.items() if count < LOW_SUPPORT_ITEM_COUNT
    }
    diagnostics = {
        "density": round(len(edges) / (len(items) * len(kc_ids)), 6) if items and kc_ids else 0.0,
        "row_sum_distribution": dict(sorted(Counter(row_sums).items())),
        "max_row_sum": max(row_sums, default=0),
        "identical_q_columns": identical_columns,
        "items_above_four_kcs": wide_rows,
        "kc_item_support": kc_support,
        "low_support_threshold": LOW_SUPPORT_ITEM_COUNT,
        "low_support_kcs": low_support,
    }
    audit = {
        "status": "PASS" if not structural_errors else "FAIL",
        "structural_errors": structural_errors,
        "items": len(items),
        "kcs": len(kc_ids),
        "one_entries": len(edges),
        "scientific_diagnostics": diagnostics,
    }
    return kc_ids, rows, edges, audit


def run(run_dir: Path, _settings: dict[str, Any] | None = None) -> dict[str, Any]:
    items = read_jsonl(run_dir / "items" / "validation" / "accepted_items.jsonl")
    cards = read_jsonl(run_dir / "kc" / "kc_inventory.jsonl")
    projections = read_jsonl(run_dir / "kc" / "cell_kc_projection.jsonl")
    kc_ids, rows, edges, audit = build(items, cards, projections)
    if audit["status"] != "PASS":
        raise RuntimeError("Q-matrix structural validation failed: " + "; ".join(audit["structural_errors"]))

    output = run_dir / "qmatrix"
    output.mkdir(parents=True, exist_ok=False)
    with (output / "q_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["item_id", *kc_ids])
        for item_id, values in rows:
            writer.writerow([item_id, *values])
    write_jsonl(output / "item_kc_edges.jsonl", sorted(edges, key=lambda row: (row["item_id"], row["kc_id"])))
    write_json(output / "audit.json", audit)
    return {"rows": len(rows), "columns": len(kc_ids), "edges": len(edges)}


def explain(run_dir: Path, item_id: str) -> dict[str, Any]:
    edges = [
        row
        for row in read_jsonl(run_dir / "qmatrix" / "item_kc_edges.jsonl")
        if row["item_id"] == item_id
    ]
    if not edges:
        raise KeyError(item_id)
    return {
        "item_id": item_id,
        "kc_ids": [row["kc_id"] for row in edges],
        "edges": edges,
        "reason": "copied deterministically from the item's frozen cell KC projection",
    }
