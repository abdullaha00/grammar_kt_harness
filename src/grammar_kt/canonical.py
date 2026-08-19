"""Deduplicate complete normalisation mappings into exact GrammarCells."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .io import read_jsonl, stable_id, write_jsonl
from .records import DIMENSIONS, grammar_cell


def build(mappings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cells_by_id: dict[str, dict[str, str]] = {}
    edges_by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for mapping in mappings:
        if mapping["result"] != "complete":
            continue
        for source_index, raw in enumerate(mapping["cells"]):
            cell = grammar_cell({key: raw[key] for key in DIMENSIONS}, label=f"{mapping['egp_id']} cell")
            canonical_json = json.dumps(
                {key: cell[key] for key in DIMENSIONS},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            cell_id = stable_id("CELL", canonical_json)
            cells_by_id[cell_id] = cell
            edges_by_cell[cell_id].append({
                "egp_id": mapping["egp_id"],
                "source_mapping_result": mapping["result"],
                "source_cell_index": source_index,
                "canonical_cell_id": cell_id,
                "source_note": mapping.get("note"),
            })
    cells = []
    for cell_id in sorted(cells_by_id):
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
    edges = sorted((row for rows in edges_by_cell.values() for row in rows), key=lambda row: (row["egp_id"], row["source_cell_index"], row["canonical_cell_id"]))
    return cells, edges


def run(run_dir: Path, _settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "canonical"
    output.mkdir(parents=True, exist_ok=False)
    cells, edges = build(read_jsonl(run_dir / "normalisation" / "final_mappings.jsonl"))
    write_jsonl(output / "canonical_cells.jsonl", cells, sort_keys=False)
    write_jsonl(output / "source_cell_edges.jsonl", edges, sort_keys=False)
    return {"canonical_cells": len(cells), "source_cell_edges": len(edges)}
