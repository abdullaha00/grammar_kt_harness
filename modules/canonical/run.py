"""Create stable exact GrammarCells from complete scalar normalization outputs."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from shared.utils.io import DIMENSIONS, ROOT, read_json, read_jsonl, require_new_directory, utc_now, write_jsonl
from shared.utils.manifests import write_stage_manifest


def canonical_json(cell: dict[str, str]) -> str:
    return json.dumps({key: cell[key] for key in DIMENSIONS}, ensure_ascii=False, separators=(",", ":"))


def stable_cell_id(cell: dict[str, str]) -> str:
    return "CELL_" + hashlib.sha256(canonical_json(cell).encode("utf-8")).hexdigest()[:16].upper()


def build(mappings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cells_by_id: dict[str, dict[str, str]] = {}
    edges_by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    validator = Draft202012Validator(read_json(ROOT / "shared" / "schemas" / "canonical_cell.schema.json"))
    for mapping in mappings:
        if mapping["result"] != "complete":
            continue
        for source_index, raw_cell in enumerate(mapping["cells"]):
            if not all(isinstance(raw_cell.get(key), str) for key in DIMENSIONS):
                raise RuntimeError(f"complete mapping contains non-scalar cell: {mapping['egp_id']}")
            cell = {key: raw_cell[key] for key in DIMENSIONS}
            errors = list(validator.iter_errors(cell))
            if errors:
                raise RuntimeError(f"invalid exact cell {mapping['egp_id']}: {errors[0].message}")
            cell_id = stable_cell_id(cell)
            if cell_id in cells_by_id and cells_by_id[cell_id] != cell:
                raise RuntimeError(f"cell ID collision: {cell_id}")
            cells_by_id[cell_id] = cell
            basis = f"{mapping['egp_id']}|{source_index}|{canonical_json(cell)}"
            edges_by_cell[cell_id].append(
                {
                    "edge_id": "EDGE_" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16].upper(),
                    "egp_id": mapping["egp_id"],
                    "source_mapping_result": mapping["result"],
                    "source_cell_index": source_index,
                    "canonical_cell_id": cell_id,
                }
            )
    cells = [
        {
            "canonical_cell_id": cell_id,
            "cell": cells_by_id[cell_id],
            "source_descriptor_count": len({row["egp_id"] for row in edges_by_cell[cell_id]}),
            "source_edge_count": len(edges_by_cell[cell_id]),
        }
        for cell_id in sorted(cells_by_id)
    ]
    edges = sorted(
        (row for values in edges_by_cell.values() for row in values),
        key=lambda row: (row["egp_id"], row["source_cell_index"], row["canonical_cell_id"]),
    )
    return cells, edges


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "canonical"
    require_new_directory(output)
    input_path = run_dir / "normalization" / "final_mappings.jsonl"
    mappings = read_jsonl(input_path)
    cells, edges = build(mappings)
    cells_path = output / "canonical_cells.jsonl"
    edges_path = output / "source_cell_edges.jsonl"
    # Preserve the accepted dimension insertion order because current stable
    # item-realization IDs were defined over Python's ordered cell rendering.
    write_jsonl(cells_path, cells, sort_keys=False)
    write_jsonl(edges_path, edges, sort_keys=False)
    write_stage_manifest(
        output,
        module="canonical",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[input_path],
        configs=[experiment_manifest, ROOT / "shared" / "schemas" / "canonical_cell.schema.json"],
        code=[Path(__file__)],
        outputs=[cells_path, edges_path],
        details={"source_cell_edges": len(edges), "canonical_cells": len(cells), "partial_mappings_expanded": False},
    )
