"""Deterministically derive item-KC edges from accepted items and KC projection."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

from .io import read_jsonl, write_json, write_jsonl


def build(items: list[dict[str, Any]], cards: list[dict[str, Any]],
          projections: list[dict[str, Any]]) -> tuple[list[str], list[tuple[str, list[int]]], list[dict[str, Any]], dict[str, Any]]:
    by_cell = {row["canonical_cell_id"]: row for row in projections}
    kc_ids = sorted(row["kc_id"] for row in cards)
    card_by_id = {row["kc_id"]: row for row in cards}
    rows, edges, errors = [], [], []
    for item in sorted(items, key=lambda row: row["item_id"]):
        expected = by_cell.get(item["canonical_cell_id"], {}).get("kc_ids", [])
        if item["all_kc_ids"] != expected:
            errors.append(f"{item['item_id']}: stored KC list differs from frozen projection")
        values = [int(kc_id in expected) for kc_id in kc_ids]
        rows.append((item["item_id"], values))
        for kc_id in expected:
            basis = f"{item['item_id']}|{kc_id}|KC_PROJECTION_v1"
            edges.append({
                "edge_id": "QEDGE_" + hashlib.sha256(basis.encode()).hexdigest()[:16].upper(),
                "item_id": item["item_id"], "kc_id": kc_id,
                "canonical_cell_id": item["canonical_cell_id"],
                "realization_id": item["realization_spec"]["realization_id"],
                "source_descriptor_ids": item["source_descriptor_ids"],
                "activation_rule": card_by_id[kc_id]["activation_rule"],
                "manual_post_hoc": False,
            })
    columns = {kc_id: tuple(values[index] for _, values in rows) for index, kc_id in enumerate(kc_ids)}
    identical = [[left, right] for index, left in enumerate(kc_ids) for right in kc_ids[index + 1:] if columns[left] == columns[right]]
    if identical:
        errors.append(f"identical Q columns: {identical}")
    row_sums = [sum(values) for _, values in rows]
    above_max = [item_id for item_id, values in rows if sum(values) > 4]
    if above_max:
        errors.append(f"rows above the accepted maximum of four KCs: {above_max}")
    audit = {
        "status": "PASS" if not errors else "FAIL", "errors": errors,
        "items": len(items), "kcs": len(kc_ids), "one_entries": len(edges),
        "density": round(len(edges) / (len(items) * len(kc_ids)), 6) if items and kc_ids else 0.0,
        "row_sum_distribution": dict(sorted(Counter(row_sums).items())),
        "max_row_sum": max(row_sums, default=0), "identical_q_columns": identical,
        "items_above_maximum": above_max,
    }
    return kc_ids, rows, edges, audit


def run(run_dir: Path) -> dict[str, Any]:
    items = read_jsonl(run_dir / "items" / "validation" / "accepted_items.jsonl")
    cards = read_jsonl(run_dir / "kc" / "kc_inventory.jsonl")
    projections = read_jsonl(run_dir / "kc" / "cell_kc_projection.jsonl")
    kc_ids, rows, edges, audit = build(items, cards, projections)
    if audit["status"] != "PASS":
        raise RuntimeError("Q-matrix validation failed: " + "; ".join(audit["errors"]))
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
    edges = [row for row in read_jsonl(run_dir / "qmatrix" / "item_kc_edges.jsonl") if row["item_id"] == item_id]
    if not edges:
        raise KeyError(item_id)
    return {"item_id": item_id, "kc_ids": [row["kc_id"] for row in edges], "edges": edges, "reason": "copied deterministically from the item's frozen cell KC projection"}
