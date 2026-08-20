"""Project a frozen KC policy onto the fixed item bank and build its Q-matrix."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

from . import kc
from .io import read_jsonl, write_json, write_jsonl
from .records import kc_opportunity


LOW_SUPPORT_ITEM_COUNT = 5


# Frozen policy projection

def _rule_scope(expression: dict[str, Any]) -> str:
    if "operation" in expression:
        return "realisation"
    if "all" in expression and any(_rule_scope(part) == "realisation" for part in expression["all"]):
        return "realisation"
    return "cell"


def project_policy(
    items: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply one already-frozen policy to each concrete accepted realization."""

    cells_by_id = {row["canonical_cell_id"]: row for row in cells}
    opportunities = []
    item_id_by_opportunity: dict[str, str] = {}
    for item in sorted(items, key=lambda row: row["item_id"]):
        cell_row = cells_by_id.get(item["canonical_cell_id"])
        if cell_row is None:
            raise RuntimeError(f"item refers to unknown canonical cell: {item['item_id']}")
        opportunity_id = item["item_opportunity_id"]
        if opportunity_id in item_id_by_opportunity:
            raise RuntimeError(f"duplicate item opportunity: {opportunity_id}")
        item_id_by_opportunity[opportunity_id] = item["item_id"]
        opportunities.append(
            kc_opportunity(
                {
                    "opportunity_id": opportunity_id,
                    "split": item["generation_metadata"]["canonical_split"],
                    "canonical_cell_id": item["canonical_cell_id"],
                    "cell": cell_row["cell"],
                    "realization_spec": item["realization_spec"],
                    "realization_operations": item["realization_evidence"]["operations"],
                    "source_descriptor_ids": item["source_descriptor_ids"],
                    "source_mapping_notes": cell_row["source_mapping_notes"],
                },
                label=f"item opportunity {opportunity_id}",
            )
        )

    materialized, cards = kc.materialize_inventory(policy, opportunities)
    projections = [
        {
            "item_id": item_id_by_opportunity[row["opportunity_id"]],
            "item_opportunity_id": row["opportunity_id"],
            "canonical_cell_id": row["canonical_cell_id"],
            "canonical_split": row["split"],
            "realization_id": row["realization_spec"]["realization_id"],
            "realization_operations": row["realization_operations"],
            "kc_ids": row["kc_ids"],
        }
        for row in materialized
    ]
    return sorted(projections, key=lambda row: row["item_id"]), cards


# Matrix integrity and scientific diagnostics

def build(
    items: list[dict[str, Any]],
    cards: list[dict[str, Any]],
    projections: list[dict[str, Any]],
) -> tuple[list[str], list[tuple[str, list[int]]], list[dict[str, Any]], dict[str, Any]]:
    """Build Q records; an uncovered item is explicit scientific output, not corruption."""

    structural_errors: list[str] = []
    item_ids = [row["item_id"] for row in items]
    kc_ids = sorted(row["kc_id"] for row in cards)
    projected_item_ids = [row["item_id"] for row in projections]
    if not items:
        structural_errors.append("no accepted items")
    if not cards:
        structural_errors.append("no projected KC inventory")
    if not projections:
        structural_errors.append("no item-level policy projections")
    if len(item_ids) != len(set(item_ids)):
        structural_errors.append("duplicate item IDs")
    if len(kc_ids) != len(set(kc_ids)):
        structural_errors.append("duplicate KC IDs")
    if len(projected_item_ids) != len(set(projected_item_ids)):
        structural_errors.append("duplicate item-level projections")
    if set(projected_item_ids) != set(item_ids):
        structural_errors.append(
            "item projection does not exactly cover accepted bank: "
            f"missing={sorted(set(item_ids) - set(projected_item_ids))}, "
            f"unknown={sorted(set(projected_item_ids) - set(item_ids))}"
        )

    projection_by_item = {row["item_id"]: row for row in projections}
    card_by_id = {row["kc_id"]: row for row in cards}
    known_kcs = set(card_by_id)
    rows: list[tuple[str, list[int]]] = []
    edges: list[dict[str, Any]] = []
    uncovered_item_ids: list[str] = []

    for item in sorted(items, key=lambda row: row["item_id"]):
        projection = projection_by_item.get(item["item_id"])
        expected = projection["kc_ids"] if projection is not None else []
        if projection is not None:
            if projection["canonical_cell_id"] != item["canonical_cell_id"]:
                structural_errors.append(f"{item['item_id']}: projected canonical cell differs")
            if projection["realization_id"] != item["realization_spec"]["realization_id"]:
                structural_errors.append(f"{item['item_id']}: projected realization differs")
        unknown = sorted(set(expected) - known_kcs)
        if unknown:
            structural_errors.append(f"{item['item_id']}: projection contains unknown KCs {unknown}")
        if not expected:
            uncovered_item_ids.append(item["item_id"])

        values = [int(kc_id in expected) for kc_id in kc_ids]
        rows.append((item["item_id"], values))
        for kc_id in expected:
            if kc_id not in card_by_id:
                continue
            rule = card_by_id[kc_id]["activation_rule"]
            edges.append(
                {
                    "item_id": item["item_id"],
                    "kc_id": kc_id,
                    "canonical_cell_id": item["canonical_cell_id"],
                    "realization_id": item["realization_spec"]["realization_id"],
                    "source_descriptor_ids": item["source_descriptor_ids"],
                    "activation_scope": _rule_scope(rule),
                    "activation_rule": rule,
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
    diagnostics = {
        "density": round(len(edges) / (len(items) * len(kc_ids)), 6) if items and kc_ids else 0.0,
        "row_sum_distribution": dict(sorted(Counter(row_sums).items())),
        "max_row_sum": max(row_sums, default=0),
        "uncovered_item_ids": uncovered_item_ids,
        "uncovered_items_by_canonical_split": dict(
            sorted(
                Counter(
                    item["generation_metadata"]["canonical_split"]
                    for item in items
                    if item["item_id"] in set(uncovered_item_ids)
                ).items()
            )
        ),
        "identical_q_columns": identical_columns,
        "items_above_four_kcs": wide_rows,
        "kc_item_support": kc_support,
        "low_support_threshold": LOW_SUPPORT_ITEM_COUNT,
        "low_support_kcs": {
            kc_id: count for kc_id, count in kc_support.items() if count < LOW_SUPPORT_ITEM_COUNT
        },
        "cell_scope_edges": sum(row["activation_scope"] == "cell" for row in edges),
        "realisation_scope_edges": sum(row["activation_scope"] == "realisation" for row in edges),
    }
    audit = {
        "status": "PASS" if not structural_errors else "FAIL",
        "structural_errors": structural_errors,
        "items": len(items),
        "covered_items": len(items) - len(uncovered_item_ids),
        "uncovered_items": len(uncovered_item_ids),
        "kcs": len(kc_ids),
        "one_entries": len(edges),
        "projection_unit": "accepted_item_realization",
        "item_labels_baked_into_generation": False,
        "scientific_diagnostics": diagnostics,
    }
    return kc_ids, rows, edges, audit


# Full stage

def run(run_dir: Path, _settings: dict[str, Any] | None = None) -> dict[str, Any]:
    items = read_jsonl(run_dir / "items" / "validation" / "accepted_items.jsonl")
    cells = read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")
    policy = kc.load_policy(run_dir / "kc_selection" / "selected_policy.json")
    projections, cards = project_policy(items, cells, policy)
    kc_ids, rows, edges, audit = build(items, cards, projections)
    if audit["status"] != "PASS":
        raise RuntimeError(
            "Q-matrix structural validation failed: " + "; ".join(audit["structural_errors"])
        )

    output = run_dir / "qmatrix"
    output.mkdir(parents=True, exist_ok=False)
    with (output / "q_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["item_id", *kc_ids])
        for item_id, values in rows:
            writer.writerow([item_id, *values])
    write_jsonl(output / "item_kc_projection.jsonl", projections)
    write_jsonl(output / "projected_kc_inventory.jsonl", sorted(cards, key=lambda row: row["kc_id"]))
    write_jsonl(
        output / "item_kc_edges.jsonl",
        sorted(edges, key=lambda row: (row["item_id"], row["kc_id"])),
    )
    write_json(output / "audit.json", audit)
    return {
        "rows": len(rows),
        "covered_rows": audit["covered_items"],
        "uncovered_rows": audit["uncovered_items"],
        "columns": len(kc_ids),
        "edges": len(edges),
    }
