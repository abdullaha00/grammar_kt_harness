"""Reproduce one learner from the reference simulator RNG stream."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.stage_8_simulation.run import _audit, _read_q, simulate_records
from shared.utils.config import resolve_experiment
from shared.utils.contracts import validate_jsonl
from shared.utils.experiment import ensure_run_metadata
from shared.utils.io import ROOT, read_json, read_jsonl, repo_path, write_json, write_jsonl
from shared.utils.manifests import describe
from shared.utils.research import prepare_unit_directory, resolve_run, safe_component


DEFAULT_LEARNER_ID = "L0001"
DEFAULT_ITEMS = Path(__file__).resolve().parent / "fixtures" / "accepted_items.jsonl"
DEFAULT_QMATRIX = Path(__file__).resolve().parent / "fixtures" / "q_matrix.csv"
DEFAULT_EXPERIMENT = "run_one_demo"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("learner_id", nargs="?", help=f"default: {DEFAULT_LEARNER_ID} with fixture inputs")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--items", type=Path, help="accepted ItemSpec JSONL")
    parser.add_argument("--qmatrix", type=Path, help="matching Q-matrix CSV")
    parser.add_argument("--upstream-run")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    using_default = args.learner_id is None
    learner_id = args.learner_id or DEFAULT_LEARNER_ID
    safe_component(learner_id)
    resolution = resolve_experiment(args.experiment)
    config = resolution.resolved
    run_dir, _ = ensure_run_metadata(resolution)
    using_explicit_files = args.items is not None or args.qmatrix is not None or using_default
    if using_explicit_files:
        if (args.items is None) != (args.qmatrix is None):
            raise ValueError("--items and --qmatrix must be supplied together")
        items_path = args.items.resolve() if args.items else DEFAULT_ITEMS
        q_path = args.qmatrix.resolve() if args.qmatrix else DEFAULT_QMATRIX
        upstream = None
    else:
        if args.upstream_run:
            upstream = resolve_run(args.upstream_run)
        elif (run_dir / "items/validation/accepted_items.jsonl").is_file():
            upstream = run_dir
        elif resolution.parent_resolved:
            upstream = resolve_run(resolution.parent_resolved["experiment_id"])
        else:
            raise FileNotFoundError(
                "simulation run-one needs frozen item/Q inputs; use --upstream-run or --items/--qmatrix"
            )
        items_path = upstream / "items/validation/accepted_items.jsonl"
        q_path = upstream / "qmatrix/q_matrix.csv"
    validate_jsonl(
        items_path,
        ROOT / "modules/stage_6_items/schemas/item_spec_v0_1.schema.json",
        label="simulation run-one input ItemSpec",
    )
    item_by_id = {row["item_id"]: row for row in read_jsonl(items_path)}
    q_kcs, q_by_item = _read_q(q_path)
    if not q_kcs or set(q_by_item) != set(item_by_id):
        raise RuntimeError("Q-matrix dimensions differ from the accepted item set")
    params_path = repo_path(config["simulation"]["config"])
    params = read_json(params_path)
    params["seed"] = int(config["simulation"]["seed"])
    observed, oracle, learners, learner_oracle = simulate_records(
        params, item_by_id, q_by_item, q_kcs, target_learner=learner_id
    )
    expected = len(item_by_id) * int(params["item_passes_per_learner"])
    audit = _audit(observed, oracle, learners, item_by_id, expected)
    unit_dir = prepare_unit_directory(run_dir / "simulation/units" / learner_id, force=args.force)
    before = {
        "learner_id": learner_id,
        "items": describe(items_path),
        "q_matrix": describe(q_path),
        "upstream_run": str(upstream) if upstream else None,
        "item_count": len(item_by_id),
        "q_columns": q_kcs,
        "item_kc_assignments": q_by_item,
    }
    write_json(unit_dir / "input.json", before)
    write_json(unit_dir / "configuration.json", {"parameters": describe(params_path), "resolved_seed": params["seed"]})
    write_jsonl(unit_dir / "observable_interactions.jsonl", observed)
    write_jsonl(unit_dir / "interactions.oracle.jsonl", oracle)
    write_json(unit_dir / "learner.json", learners[0])
    write_json(unit_dir / "learner.oracle.json", learner_oracle[0])
    write_json(unit_dir / "validation.json", audit)
    after = {
        "learner": learners[0],
        "observable_events": len(observed),
        "first_observable_event": observed[0],
        "last_observable_event": observed[-1],
        "validation": audit,
    }
    print(
        json.dumps(
            {"before": before, "after": after, "unit_directory": str(unit_dir)},
            indent=2,
        )
    )
    return 0 if audit["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
