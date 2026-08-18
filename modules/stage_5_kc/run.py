"""Build one exact opportunity per cell and apply the selected KC policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from modules.stage_5_kc.policy import load_policy, materialize
from shared.utils.contracts import validate_jsonl, validate_value
from shared.utils.io import ROOT, read_jsonl, repo_path, utc_now, write_jsonl
from shared.utils.manifests import write_stage_manifest
from shared.utils.research import prepare_stage_directory


OPPORTUNITY_FIELDS = (
    "opportunity_id",
    "split",
    "canonical_cell_id",
    "cell",
    "realization_spec",
    "realization_operations",
    "source_descriptor_ids",
    "source_mapping_notes",
)


def declared_opportunity(value: dict[str, Any]) -> dict[str, Any]:
    """Project an input onto the KC contract so prior KC labels cannot leak in."""
    return {field: value[field] for field in OPPORTUNITY_FIELDS}


def validate_opportunity(value: dict[str, Any], *, label: str) -> None:
    validate_value(
        value,
        ROOT / "modules/stage_5_kc/schemas/opportunity.schema.json",
        label=label,
    )
    validate_value(
        value["cell"],
        ROOT / "modules/stage_3_canonical/schemas/grammar_cell.schema.json",
        label=f"{label} GrammarCell",
    )
    validate_value(
        value["realization_spec"],
        ROOT / "modules/stage_4_realization/schemas/realization_spec_v0.schema.json",
        label=f"{label} RealizationSpec",
    )
    if set(value["source_mapping_notes"]) != set(value["source_descriptor_ids"]):
        raise ValueError(f"{label}: source notes do not match source descriptor IDs")


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "kc"
    prepare_stage_directory(output)
    cells_path = run_dir / "canonical" / "canonical_cells.jsonl"
    realizations_path = run_dir / "realization" / "realizations.jsonl"
    policy_name = config["policy"]
    try:
        policy_path = repo_path(config["policies"][policy_name])
    except KeyError as error:
        raise ValueError(f"unknown configured KC policy: {policy_name}") from error
    policy = load_policy(policy_path)
    record_schema = ROOT / "modules/stage_3_canonical/schemas/grammar_cell_record.schema.json"
    validate_jsonl(cells_path, record_schema, label="KC input GrammarCellRecord")
    cell_rows = {row["canonical_cell_id"]: row for row in read_jsonl(cells_path)}
    grammar_cell_schema = ROOT / "modules/stage_3_canonical/schemas/grammar_cell.schema.json"
    realization_schema = ROOT / "modules/stage_4_realization/schemas/realization_spec_v0.schema.json"
    for row in cell_rows.values():
        validate_value(row.get("cell"), grammar_cell_schema, label="KC input GrammarCell")
    cells = {cell_id: row["cell"] for cell_id, row in cell_rows.items()}
    selected: dict[str, dict[str, Any]] = {}
    realization_rows = read_jsonl(realizations_path)
    for row in realization_rows:
        validate_value(row.get("spec"), realization_schema, label="KC input RealizationSpec")
    for row in sorted(realization_rows, key=lambda value: value["spec"]["realization_id"]):
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
                "split": realization["split"],
                "canonical_cell_id": cell_id,
                "cell": cells[cell_id],
                "realization_spec": realization["spec"],
                "realization_operations": realization["derivation"]["operations"],
                "source_descriptor_ids": cell_rows[cell_id]["source_descriptor_ids"],
                "source_mapping_notes": cell_rows[cell_id]["source_mapping_notes"],
            }
        )
    for opportunity in opportunities:
        validate_opportunity(opportunity, label="KC input opportunity")
    projections, cards = materialize(policy, opportunities)
    if any(not row["kc_ids"] for row in projections):
        empty = [row["canonical_cell_id"] for row in projections if not row["kc_ids"]]
        raise RuntimeError(f"KC policy leaves cells uncovered: {empty}")
    inventory_path = output / "kc_inventory.jsonl"
    projection_path = output / "cell_kc_projection.jsonl"
    write_jsonl(inventory_path, sorted(cards, key=lambda row: row["kc_id"]))
    write_jsonl(projection_path, sorted(projections, key=lambda row: row["opportunity_id"]))
    kc_schema = ROOT / "modules/stage_5_kc/schemas/kc_spec.schema.json"
    activation_schema = ROOT / "modules/stage_5_kc/schemas/kc_activation.schema.json"
    opportunity_schema = ROOT / "modules/stage_5_kc/schemas/opportunity.schema.json"
    validate_jsonl(inventory_path, kc_schema, label="KC output KCSpec")
    validate_jsonl(projection_path, activation_schema, label="KC output KCActivation")
    write_stage_manifest(
        output,
        module="kc",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[cells_path, realizations_path],
        configs=[
            experiment_manifest, policy_path, grammar_cell_schema, record_schema,
            realization_schema, opportunity_schema, kc_schema, activation_schema,
        ],
        code=[Path(__file__), ROOT / "modules" / "stage_5_kc" / "policy.py"],
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply one KC policy to a small opportunity fixture set.")
    parser.add_argument("--input", type=Path, default=ROOT / "modules/stage_5_kc/fixtures/core.jsonl")
    parser.add_argument("--experiment", default="current")
    parser.add_argument("--policy", choices=("factorized", "full_cell", "factorized_plus_interactions"))
    args = parser.parse_args()
    from shared.utils.config import resolve_experiment
    from modules.stage_5_kc.policy import explain_policy

    config = resolve_experiment(args.experiment).resolved["kc"]
    policy_name = args.policy or config["policy"]
    policy = load_policy(repo_path(config["policies"][policy_name]))
    opportunities = []
    fixture_labels: dict[str, str] = {}
    for raw in read_jsonl(args.input.resolve()):
        raw.setdefault(
            "source_mapping_notes",
            {source_id: None for source_id in raw["source_descriptor_ids"]},
        )
        opportunity = declared_opportunity(raw)
        validate_opportunity(opportunity, label=f"KC fixture {raw.get('fixture_label', raw['opportunity_id'])}")
        opportunities.append(opportunity)
        fixture_labels[opportunity["opportunity_id"]] = raw.get("fixture_label", opportunity["opportunity_id"])
    projections, cards = materialize(policy, opportunities)
    for projection in projections:
        validate_value(
            projection,
            ROOT / "modules/stage_5_kc/schemas/kc_activation.schema.json",
            label="KC fixture output KCActivation",
        )
    for card in cards:
        validate_value(
            card,
            ROOT / "modules/stage_5_kc/schemas/kc_spec.schema.json",
            label="KC fixture output KCSpec",
        )
    result = {
        "policy": policy_name,
        "projections": projections,
        "kc_specs": cards,
        "explanations": [
            {
                "fixture_label": fixture_labels[row["opportunity_id"]],
                **explain_policy(policy, row),
            }
            for row in opportunities
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
