"""Deduplicate complete normalisation mappings into exact GrammarCells."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..io import read_jsonl, stable_id, write_json, write_jsonl
from ..records import DIMENSIONS, grammar_cell


def build(mappings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cells_by_id: dict[str, dict[str, str]] = {}
    edges_by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # Validate every exact cell in complete mappings, derive its stable ID, and deduplicate it.
    # Example mapping:
    # {
    #     "egp_id": "FIX_CANONICAL",
    #     "result": "complete",
    #     "cells": [{"tense": "past", "aspect": "none", "voice": "passive",
    #                "polarity": "positive", "clause": "declarative", "modal": "none"}],
    #     "note": None,
    # }
    for mapping in mappings:
        if mapping["result"] != "complete":
            continue
        # `source_index` is the cell's position in the source mapping; `raw` is one
        # six-dimensional cell such as {"tense": "past", ..., "modal": "none"}.
        for source_index, raw in enumerate(mapping["cells"]):
            cell = grammar_cell({key: raw[key] for key in DIMENSIONS}, label=f"{mapping['egp_id']} cell")
            canonical_json = json.dumps(
                {key: cell[key] for key in DIMENSIONS},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            cell_id = stable_id("CELL", canonical_json)
            cells_by_id[cell_id] = cell
            # Keep the source descriptor and its original cell position even when
            # several sources collapse to the same canonical cell ID.
            edges_by_cell[cell_id].append({
                "egp_id": mapping["egp_id"],
                "source_mapping_result": mapping["result"],
                "source_cell_index": source_index,
                "canonical_cell_id": cell_id,
                "source_note": mapping.get("note"),
            })

    # Aggregate all descriptor support onto each deduplicated GrammarCell.
    cells = []
    for cell_id in sorted(cells_by_id):
        # For example, `rows` may contain edges from descriptors EGP_A and EGP_B
        # that both specify the same past/passive/positive/declarative cell.
        rows = edges_by_cell[cell_id]
        ids = sorted({row["egp_id"] for row in rows})
        cells.append({
            "canonical_cell_id": cell_id,
            "cell": cells_by_id[cell_id],
            "source_descriptor_count": len(ids),
            "source_edge_count": len(rows),
            "source_descriptor_ids": ids,
            "source_mapping_notes": {source_id: next(row["source_note"] for row in rows if row["egp_id"] == source_id) for source_id in ids},
        })

    # Retain one explicit source-to-cell edge for every source mapping cell.
    edges = sorted((row for rows in edges_by_cell.values() for row in rows), key=lambda row: (row["egp_id"], row["source_cell_index"], row["canonical_cell_id"]))
    return cells, edges


def run(run_dir: Path, _settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "canonical"
    output.mkdir(parents=True, exist_ok=False)
    mappings = read_jsonl(run_dir / "normalisation" / "final_mappings.jsonl")
    cells, edges = build(mappings)
    write_jsonl(output / "canonical_cells.jsonl", cells, sort_keys=False)
    write_jsonl(output / "source_cell_edges.jsonl", edges, sort_keys=False)
    counts = Counter(row["result"] for row in mappings)
    contributing = sorted(
        row["egp_id"]
        for row in mappings
        if row["result"] == "complete" and row.get("cells")
    )
    non_contributing = [
        {
            "egp_id": row["egp_id"],
            "reason": (
                "complete_without_cells"
                if row["result"] == "complete"
                else row["result"]
            ),
        }
        for row in mappings
        if row["egp_id"] not in set(contributing)
    ]
    audit = {
        "source_descriptors": len(mappings),
        "normalisation_result_classes": {
            name: counts.get(name, 0)
            for name in ("complete", "partial", "out_of_scope", "unresolved", "schema_failure")
        },
        "complete_descriptors_contributing_cells": len(contributing),
        "contributing_descriptor_ids": contributing,
        "non_contributing_descriptors": non_contributing,
        "source_cell_edges": len(edges),
        "canonical_cell_count": len(cells),
        "edge_to_unique_cell_ratio": len(edges) / len(cells) if cells else None,
        "deduplication_ratio": len(cells) / len(edges) if edges else None,
        "deduplication_reduction": 1.0 - (len(cells) / len(edges)) if edges else None,
        "partial_mappings_contribute_exact_cells": False,
    }
    write_json(output / "audit.json", audit)
    return {
        "canonical_cells": len(cells),
        "source_cell_edges": len(edges),
        "contributing_descriptors": len(contributing),
    }
