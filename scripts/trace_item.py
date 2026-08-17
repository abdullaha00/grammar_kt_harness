#!/usr/bin/env python3
"""Print one accepted item's source-to-interaction lineage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.utils.io import read_jsonl


def _one(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get(key) == value), None)


def _indexed_mappings(run_dir: Path, phase: int) -> dict[str, dict[str, Any]]:
    values = read_jsonl(run_dir / "normalization" / f"phase{phase}.jsonl")
    index = read_jsonl(run_dir / "normalization" / f"phase{phase}_index.jsonl")
    if len(values) != len(index):
        raise RuntimeError(f"Phase {phase} values/index length mismatch")
    return {
        meta["unit_id"]: {"index": meta, "mapping": mapping}
        for meta, mapping in zip(index, values, strict=True)
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("item_id")
    parser.add_argument("--run", required=True, help="run ID under runs/ or a run-directory path")
    parser.add_argument("--interaction-limit", type=int, default=5)
    args = parser.parse_args()
    run_dir = Path(args.run)
    if not run_dir.is_absolute() and len(run_dir.parts) == 1:
        run_dir = ROOT / "runs" / run_dir
    run_dir = run_dir.resolve()
    items = read_jsonl(run_dir / "items" / "validation" / "accepted_items.jsonl")
    item = _one(items, "item_id", args.item_id)
    if item is None:
        raise SystemExit(f"accepted item not found: {args.item_id}")

    source_by_id = {row["egp_id"]: row for row in read_jsonl(run_dir / "source" / "source_subset.jsonl")}
    final_by_id = {row["egp_id"]: row for row in read_jsonl(run_dir / "normalization" / "final_mappings.jsonl")}
    mapping_prov = {row["egp_id"]: row for row in read_jsonl(run_dir / "normalization" / "mapping_provenance.jsonl")}
    phase1 = _indexed_mappings(run_dir, 1)
    phase2 = _indexed_mappings(run_dir, 2)
    cell = _one(read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl"), "canonical_cell_id", item["canonical_cell_id"])
    cell_edges = [
        row for row in read_jsonl(run_dir / "canonical" / "source_cell_edges.jsonl")
        if row["canonical_cell_id"] == item["canonical_cell_id"]
    ]
    base_realizations = [
        row for row in read_jsonl(run_dir / "realization" / "realizations.jsonl")
        if row["spec"]["canonical_cell_id"] == item["canonical_cell_id"]
    ]
    q_edges = [
        row for row in read_jsonl(run_dir / "qmatrix" / "item_kc_edges.jsonl")
        if row["item_id"] == item["item_id"]
    ]
    interactions = [
        row for row in read_jsonl(run_dir / "simulation" / "observable_interactions.jsonl")
        if row["item_id"] == item["item_id"]
    ]
    source_trace = []
    for egp_id in item["source_descriptor_ids"]:
        provenance = mapping_prov[egp_id]
        unit_id = provenance["primary_unit_id"]
        source_trace.append(
            {
                "source_descriptor": source_by_id[egp_id],
                "phase1": phase1[unit_id],
                "phase2": phase2.get(unit_id),
                "final_mapping": final_by_id[egp_id],
            }
        )
    result = {
        "item_id": item["item_id"],
        "chain": {
            "source_descriptors_to_normalization": source_trace,
            "canonical_cell": cell,
            "source_cell_edges": cell_edges,
            "base_realizations_for_cell": base_realizations,
            "item_realization_spec": item["realization_spec"],
            "accepted_item": item,
            "item_kc_edges": q_edges,
            "selected_observable_interactions": interactions[: max(0, args.interaction_limit)],
            "total_observable_interactions_for_item": len(interactions),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
