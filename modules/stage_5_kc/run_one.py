"""Apply one declared KC policy to one canonical opportunity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from modules.stage_5_kc.policy import explain_policy, load_policy, materialize
from modules.stage_5_kc.run import declared_opportunity, validate_opportunity
from shared.utils.config import resolve_experiment
from shared.utils.contracts import validate_value
from shared.utils.experiment import ensure_run_metadata
from shared.utils.io import read_json, read_jsonl, repo_path, write_json
from shared.utils.manifests import describe
from shared.utils.research import prepare_unit_directory, resolve_run, safe_component


DEFAULT_CELL_ID = "CELL_0000000000000001"
DEFAULT_INPUT = Path(__file__).resolve().parent / "fixtures" / "core.jsonl"
DEFAULT_EXPERIMENT = "run_one_demo"


def _upstream_run(resolution: Any, requested: str | None, run_dir: Path) -> Path:
    if requested:
        return resolve_run(requested)
    if (run_dir / "canonical/canonical_cells.jsonl").is_file():
        return run_dir
    parent = resolution.parent_resolved
    if parent and parent.get("experiment_id"):
        return resolve_run(parent["experiment_id"])
    raise FileNotFoundError("KC run-one needs canonical/realization outputs; use --upstream-run or --input")


def opportunity_from_run(cell_id: str, upstream: Path) -> dict[str, Any]:
    cell_row = next(
        row for row in read_jsonl(upstream / "canonical/canonical_cells.jsonl")
        if row["canonical_cell_id"] == cell_id
    )
    realizations = sorted(
        (
            row for row in read_jsonl(upstream / "realization/realizations.jsonl")
            if row["spec"]["canonical_cell_id"] == cell_id
        ),
        key=lambda row: row["spec"]["realization_id"],
    )
    if not realizations:
        raise KeyError(f"no realization for {cell_id}")
    selected = realizations[0]
    basis = f"{cell_id}|{selected['spec']['realization_id']}"
    return {
        "opportunity_id": "OPP_" + hashlib.sha256(basis.encode()).hexdigest()[:16].upper(),
        "split": selected["split"],
        "canonical_cell_id": cell_id,
        "cell": cell_row["cell"],
        "realization_spec": selected["spec"],
        "realization_operations": selected["derivation"]["operations"],
        "source_descriptor_ids": cell_row["source_descriptor_ids"],
        "source_mapping_notes": cell_row["source_mapping_notes"],
    }


def run_one(
    cell_id: str,
    *,
    experiment: str | Path,
    input_path: Path | None = None,
    upstream_run: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    safe_component(cell_id)
    resolution = resolve_experiment(experiment)
    run_dir, _ = ensure_run_metadata(resolution)
    config = resolution.resolved["kc"]
    policy_name = config["policy"]
    policy_path = repo_path(config["policies"][policy_name])
    policy = load_policy(policy_path)
    if input_path:
        explicit = input_path.resolve()
        if explicit.suffix == ".jsonl":
            opportunity = next(
                row for row in read_jsonl(explicit)
                if row["canonical_cell_id"] == cell_id
            )
        else:
            opportunity = read_json(explicit)
        upstream = None
    else:
        upstream = _upstream_run(resolution, upstream_run, run_dir)
        opportunity = opportunity_from_run(cell_id, upstream)
    if opportunity["canonical_cell_id"] != cell_id:
        raise ValueError("explicit opportunity does not match requested cell")
    opportunity.setdefault(
        "source_mapping_notes",
        {source_id: None for source_id in opportunity["source_descriptor_ids"]},
    )
    opportunity = declared_opportunity(opportunity)
    validate_opportunity(opportunity, label="KC run-one input opportunity")
    projections, cards = materialize(policy, [opportunity])
    validate_value(
        projections[0],
        repo_path("modules/stage_5_kc/schemas/kc_activation.schema.json"),
        label="KC run-one output KCActivation",
    )
    for card in cards:
        validate_value(
            card,
            repo_path("modules/stage_5_kc/schemas/kc_spec.schema.json"),
            label="KC run-one output KCSpec",
        )
    explanation = explain_policy(policy, opportunity)
    unit_dir = prepare_unit_directory(run_dir / "kc" / "units" / cell_id, force=force)
    write_json(unit_dir / "input.json", opportunity)
    write_json(
        unit_dir / "configuration.json",
        {
            "kc_version": config["version"],
            "policy_name": policy_name,
            "policy": describe(policy_path),
            "upstream_run": str(upstream) if upstream else None,
        },
    )
    result = {"projection": projections[0], "kc_specs": cards}
    write_json(unit_dir / "output.json", result)
    write_json(unit_dir / "explanation.json", explanation)
    return {
        "before": opportunity,
        "after": result,
        **result,
        "explanation": explanation,
        "unit_directory": str(unit_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cell_id", nargs="?", help=f"default: {DEFAULT_CELL_ID} from the core fixture")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--upstream-run")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    using_default = args.cell_id is None
    result = run_one(
        args.cell_id or DEFAULT_CELL_ID,
        experiment=args.experiment,
        input_path=args.input or (DEFAULT_INPUT if using_default else None),
        upstream_run=args.upstream_run,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
