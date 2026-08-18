"""Show one item's generation, deterministic validation, and model diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shared.utils.io import read_json, read_jsonl
from shared.utils.manifests import describe
from shared.utils.research import resolve_run


def _show(title: str, value: Any) -> None:
    print(f"\n== {title} ==")
    if isinstance(value, str):
        print(value.rstrip())
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _legacy_inspect(run: Path, item_id: str) -> None:
    """Read the accepted pre-refactor layout without mutating or importing it."""

    accepted_path = run / "items/validated/items_v1.jsonl"
    item = next(row for row in read_jsonl(accepted_path) if row["item_id"] == item_id)
    opportunity_path = run / "kc/inventory/OPPORTUNITY_PROJECTION_v1.jsonl"
    inventory_path = run / "kc/inventory/KC_INVENTORY_v1.jsonl"
    realization_path = run / "realization/outputs/realizations_v1.jsonl"
    candidate_path = run / "items/pilots/v0_1/candidates.jsonl"
    hard_path = run / "items/pilots/v0_1/all/deterministic_validation.jsonl"
    units_path = run / "items/pilots/v0_1/validation_units.jsonl"
    opportunity = next(
        row for row in read_jsonl(opportunity_path)
        if row["opportunity_id"] == item["provenance"]["opportunity_id"]
    )
    primary_kc = next(
        row for row in read_jsonl(inventory_path)
        if row["kc_id"] == item["primary_kc_id"]
    )
    realizations = [
        row for row in read_jsonl(realization_path)
        if row["spec"]["canonical_cell_id"] == item["canonical_cell_id"]
    ]
    candidate = next(row for row in read_jsonl(candidate_path) if row["item_id"] == item_id)
    hard = next(row for row in read_jsonl(hard_path) if row["item_id"] == item_id)
    unit = next(
        row for row in read_jsonl(units_path)
        if row["item_id"] == item_id and row["duplicate_of"] is None
    )
    uid = unit["validation_unit_id"]
    prompt_path = run / f"logs/items/model_validation_items_v0_1/{uid}.attempt-01.prompt.txt"
    invocation_path = run / f"logs/items/model_validation_items_v0_1/{uid}.attempt-01.json"
    raw_path = run / f"items/pilots/v0_1/model_validation/raw/{uid}.attempt-01.txt"
    parsed_path = run / f"items/pilots/v0_1/model_validation/parsed/{uid}.json"
    _show(
        "Evidence layout",
        {
            "kind": "legacy_accepted_reference_read_only",
            "root": str(run),
            "note": "Historical evidence is displayed in place; it is not represented as a new harness run.",
        },
    )
    _show(
        "Cell, realization, KC, and generation input",
        {
            "opportunity": opportunity,
            "primary_kc": primary_kc,
            "realizations_for_cell": realizations,
            "batch_input_artifacts": [
                describe(opportunity_path), describe(inventory_path), describe(realization_path)
            ],
        },
    )
    _show(
        "Generation procedure/configuration",
        {
            "deterministic": True,
            "template": describe(run / "items/templates/controlled_transformation_v0_1.txt"),
            "item_method": describe(run / "items/specification/ITEM_METHOD_v0_1.md"),
            "model_invoked": False,
        },
    )
    _show("Generated item", candidate)
    _show(
        "Deterministic and final validation",
        {
            "deterministic": hard,
            "accepted_item": item,
            "accept_reject_reason": "accepted: deterministic checks and independent automated diagnostic passed",
            "automated_not_human_validation": True,
        },
    )
    _show("Independent model diagnostic input", candidate)
    _show("Independent model rendered prompt", prompt_path.read_text(encoding="utf-8"))
    _show("Independent model invocation", read_json(invocation_path))
    _show("Independent model raw output", raw_path.read_text(encoding="utf-8"))
    _show("Independent model parsed output", read_json(parsed_path))
    _show(
        "Independent model harness validation",
        {
            "accepted_output": item["validator_results"]["independent_automated_diagnostic"],
            "automated_not_human_validation": True,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("item_id")
    parser.add_argument("--experiment", default="current")
    parser.add_argument("--run")
    args = parser.parse_args()
    run = resolve_run(args.run or args.experiment)
    generation = run / "items/generation/units" / args.item_id
    if not generation.is_dir():
        if (run / "items/validated/items_v1.jsonl").is_file():
            _legacy_inspect(run, args.item_id)
            return 0
        raise FileNotFoundError(f"item generation evidence not found: {generation}")
    _show("Cell, realization, KC, and generation input", read_json(generation / "input.json"))
    _show("Generation procedure/configuration", read_json(generation / "procedure.json"))
    _show("Generated item", read_json(generation / "generated_item.json"))
    validation_path = run / "items/validation/units" / f"{args.item_id}.json"
    _show("Deterministic and final validation", read_json(validation_path))
    units = read_jsonl(run / "items/generation/validation_units.jsonl")
    diagnostic = next(
        (row for row in units if row["item_id"] == args.item_id and row["duplicate_of"] is None),
        None,
    )
    if diagnostic:
        model_unit = run / "items/units" / diagnostic["validation_unit_id"]
        _show("Independent model diagnostic input", read_json(model_unit / "input.json"))
        _show("Independent model rendered prompt", (model_unit / "rendered_prompt.txt").read_text(encoding="utf-8"))
        _show("Independent model invocation", read_json(model_unit / "invocation.json"))
        _show("Independent model raw output", (model_unit / "raw_output.txt").read_text(encoding="utf-8"))
        _show("Independent model parsed output", read_json(model_unit / "parsed_output.json"))
        _show("Independent model harness validation", read_json(model_unit / "validation.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
