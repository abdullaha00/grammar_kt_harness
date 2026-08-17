"""Recompute item KC activation and export the deterministic item-by-KC matrix."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from io import StringIO
from pathlib import Path
from typing import Any

from modules.kc.policy import activated_kcs, load_policy
from modules.realization.engine import realize
from shared.utils.io import ROOT, read_jsonl, repo_path, require_new_directory, utc_now, write_json, write_jsonl
from shared.utils.manifests import write_stage_manifest


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "qmatrix"
    require_new_directory(output)
    items_path = run_dir / "items" / "validation" / "accepted_items.jsonl"
    inventory_path = run_dir / "kc" / "kc_inventory.jsonl"
    cells_path = run_dir / "canonical" / "canonical_cells.jsonl"
    lexicon_path = repo_path(config["_realization"]["lexicon"])
    policy_name = config["_kc"]["policy"]
    policy_path = repo_path(config["_kc"]["policies"][policy_name])
    policy = load_policy(policy_path)
    items = read_jsonl(items_path)
    cards = read_jsonl(inventory_path)
    cells = {row["canonical_cell_id"]: row["cell"] for row in read_jsonl(cells_path)}
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(lexicon_path)}
    kc_ids = sorted(row["kc_id"] for row in cards)
    card_by_id = {row["kc_id"]: row for row in cards}
    errors: list[str] = []
    matrix_rows: list[tuple[str, list[int]]] = []
    edges = []
    for item in sorted(items, key=lambda row: row["item_id"]):
        cell = cells[item["canonical_cell_id"]]
        spec = item["realization_spec"]
        derivation = realize(spec, cell, frames[spec["predicate_frame_id"]])
        opportunity = {
            "canonical_cell_id": item["canonical_cell_id"],
            "cell": cell,
            "realization_operations": derivation["operations"],
        }
        expected = activated_kcs(policy, opportunity)
        if item["all_kc_ids"] != expected:
            errors.append(f"{item['item_id']}: stored KC list differs from rederived activation")
        if not expected or not set(expected) <= set(kc_ids):
            errors.append(f"{item['item_id']}: empty or unknown rederived KC set")
        values = [int(kc_id in expected) for kc_id in kc_ids]
        matrix_rows.append((item["item_id"], values))
        for kc_id in expected:
            basis = f"{item['item_id']}|{kc_id}|KC_PROJECTION_v1"
            edges.append(
                {
                    "edge_id": "QEDGE_" + hashlib.sha256(basis.encode()).hexdigest()[:16].upper(),
                    "item_id": item["item_id"],
                    "kc_id": kc_id,
                    "canonical_cell_id": item["canonical_cell_id"],
                    "realization_id": spec["realization_id"],
                    "source_descriptor_ids": item["source_descriptor_ids"],
                    "activation_rule": card_by_id[kc_id]["activation_rule"],
                    "kc_projection_version": "KC_PROJECTION_v1",
                    "manual_post_hoc": False,
                }
            )
    if len(edges) != sum(sum(values) for _, values in matrix_rows):
        errors.append("Q edge count differs from matrix one-entry count")
    columns = {
        kc_id: tuple(values[index] for _, values in matrix_rows)
        for index, kc_id in enumerate(kc_ids)
    }
    identical = [
        [left, right]
        for index, left in enumerate(kc_ids)
        for right in kc_ids[index + 1 :]
        if columns[left] == columns[right]
    ]
    if identical:
        errors.append(f"identical Q columns: {identical}")
    maximum = int(config["max_kcs_per_item"])
    above_max = [item_id for item_id, values in matrix_rows if sum(values) > maximum]
    if above_max:
        errors.append(f"rows above configured maximum {maximum}: {above_max}")
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["item_id", *kc_ids])
    for item_id_value, values in matrix_rows:
        writer.writerow([item_id_value, *values])
    matrix_path = output / "q_matrix.csv"
    edges_path = output / "item_kc_edges.jsonl"
    audit_path = output / "audit.json"
    matrix_path.write_text(buffer.getvalue(), encoding="utf-8")
    write_jsonl(edges_path, sorted(edges, key=lambda row: (row["item_id"], row["kc_id"])))
    row_sums = [sum(values) for _, values in matrix_rows]
    audit = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "items": len(items),
        "kcs": len(kc_ids),
        "one_entries": len(edges),
        "density": round(len(edges) / (len(items) * len(kc_ids)), 6) if items and kc_ids else 0.0,
        "row_sum_distribution": dict(sorted(Counter(row_sums).items())),
        "max_row_sum": max(row_sums, default=0),
        "items_above_configured_max": above_max,
        "identical_q_columns": identical,
        "always_coactive_kc_pairs": identical,
        "manual_post_hoc_edges": 0,
    }
    write_json(audit_path, audit)
    if errors:
        raise RuntimeError("Q-matrix contract failed: " + "; ".join(errors))
    write_stage_manifest(
        output,
        module="qmatrix",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[items_path, inventory_path, cells_path],
        configs=[experiment_manifest, policy_path, lexicon_path],
        code=[Path(__file__), ROOT / "modules" / "kc" / "policy.py", ROOT / "modules" / "realization" / "engine.py"],
        outputs=[matrix_path, edges_path, audit_path],
        details={"q_rows": len(items), "q_columns": len(kc_ids), "q_edges": len(edges), "manual_assignments": 0},
    )

