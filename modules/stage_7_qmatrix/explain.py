"""Explain one Q-matrix row from frozen item/KC activation evidence."""

from __future__ import annotations

import argparse
import csv
import json

from shared.utils.io import read_jsonl
from shared.utils.research import resolve_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("item_id")
    parser.add_argument("--experiment", default="current", help="run ID unless --run is supplied")
    parser.add_argument("--run")
    args = parser.parse_args()
    run = resolve_run(args.run or args.experiment)
    modern = (run / "qmatrix/q_matrix.csv").is_file()
    matrix_path = run / ("qmatrix/q_matrix.csv" if modern else "qmatrix/outputs/q_matrix.csv")
    items_path = run / (
        "items/validation/accepted_items.jsonl" if modern else "items/validated/items_v1.jsonl"
    )
    projection_path = run / (
        "kc/cell_kc_projection.jsonl" if modern else "kc/inventory/OPPORTUNITY_PROJECTION_v1.jsonl"
    )
    edges_path = run / (
        "qmatrix/item_kc_edges.jsonl" if modern else "qmatrix/outputs/item_kc_edges.jsonl"
    )
    with matrix_path.open(newline="", encoding="utf-8") as handle:
        row = next((value for value in csv.DictReader(handle) if value["item_id"] == args.item_id), None)
    if row is None:
        raise KeyError(f"Q-matrix item not found: {args.item_id}")
    item = next(
        value for value in read_jsonl(items_path)
        if value["item_id"] == args.item_id
    )
    projection = next(
        value for value in read_jsonl(projection_path)
        if value["canonical_cell_id"] == item["canonical_cell_id"]
    )
    edges = [
        value for value in read_jsonl(edges_path)
        if value["item_id"] == args.item_id
    ]
    result = {
        "item_id": args.item_id,
        "evidence_layout": "research_harness" if modern else "legacy_accepted_reference_read_only",
        "q_row": row,
        "frozen_item_opportunity": {
            "canonical_cell_id": item["canonical_cell_id"],
            "realization_spec": item["realization_spec"],
            "stored_item_kcs": item["all_kc_ids"],
        },
        "frozen_kc_activation": projection,
        "edges": [
            {
                **edge,
                "deterministic_reason": (
                    "KC appears in the frozen cell opportunity activation; "
                    "Q-matrix performs no manual or post-hoc assignment"
                ),
            }
            for edge in edges
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
