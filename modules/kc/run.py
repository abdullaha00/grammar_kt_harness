"""Build one exact opportunity per cell and apply the selected KC policy."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from modules.kc.policy import load_policy, materialize
from shared.utils.io import ROOT, read_jsonl, repo_path, require_new_directory, utc_now, write_jsonl
from shared.utils.manifests import write_stage_manifest


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "kc"
    require_new_directory(output)
    cells_path = run_dir / "canonical" / "canonical_cells.jsonl"
    edges_path = run_dir / "canonical" / "source_cell_edges.jsonl"
    realizations_path = run_dir / "realization" / "realizations.jsonl"
    splits_path = run_dir / "realization" / "cell_splits.jsonl"
    policy_name = config["policy"]
    try:
        policy_path = repo_path(config["policies"][policy_name])
    except KeyError as error:
        raise ValueError(f"unknown configured KC policy: {policy_name}") from error
    policy = load_policy(policy_path)
    cells = {row["canonical_cell_id"]: row["cell"] for row in read_jsonl(cells_path)}
    splits = {row["canonical_cell_id"]: row["split"] for row in read_jsonl(splits_path)}
    edges = read_jsonl(edges_path)
    source_ids: dict[str, list[str]] = {}
    for edge in edges:
        source_ids.setdefault(edge["canonical_cell_id"], []).append(edge["egp_id"])
    selected: dict[str, dict[str, Any]] = {}
    for row in sorted(read_jsonl(realizations_path), key=lambda value: value["spec"]["realization_id"]):
        selected.setdefault(row["spec"]["canonical_cell_id"], row)
    if set(selected) != set(cells):
        raise RuntimeError("KC opportunities lack exactly one selectable realization per cell")
    opportunities = []
    for cell_id in sorted(selected):
        realization = selected[cell_id]
        basis = f"{cell_id}|{realization['spec']['realization_id']}"
        opportunities.append(
            {
                "opportunity_id": "OPP_" + hashlib.sha256(basis.encode()).hexdigest()[:16].upper(),
                "split": splits[cell_id],
                "canonical_cell_id": cell_id,
                "cell": cells[cell_id],
                "realization_spec": realization["spec"],
                "realization_operations": realization["derivation"]["operations"],
                "source_descriptor_ids": sorted(set(source_ids[cell_id])),
            }
        )
    projections, cards = materialize(policy, opportunities)
    if any(not row["kc_ids"] for row in projections):
        empty = [row["canonical_cell_id"] for row in projections if not row["kc_ids"]]
        raise RuntimeError(f"KC policy leaves cells uncovered: {empty}")
    inventory_path = output / "kc_inventory.jsonl"
    projection_path = output / "cell_kc_projection.jsonl"
    write_jsonl(inventory_path, sorted(cards, key=lambda row: row["kc_id"]))
    write_jsonl(projection_path, sorted(projections, key=lambda row: row["opportunity_id"]))
    write_stage_manifest(
        output,
        module="kc",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[cells_path, edges_path, realizations_path, splits_path],
        configs=[experiment_manifest, policy_path],
        code=[Path(__file__), ROOT / "modules" / "kc" / "policy.py"],
        outputs=[inventory_path, projection_path],
        details={
            "policy": policy_name,
            "policy_id": policy["policy_id"],
            "canonical_cells": len(projections),
            "kcs": len(cards),
            "downstream_signals_used": [],
            "cognitive_validity_claimed": False,
        },
    )

