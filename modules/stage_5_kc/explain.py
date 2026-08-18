"""Explain activated and non-activated KC rules for one cell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.stage_5_kc.policy import explain_policy, load_policy
from modules.stage_5_kc.run_one import opportunity_from_run
from shared.utils.config import resolve_experiment
from shared.utils.io import read_json, repo_path
from shared.utils.research import resolve_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cell_id")
    parser.add_argument("--experiment", default="current")
    parser.add_argument("--run", help="run providing the frozen canonical/realization input")
    parser.add_argument("--compare-policy", choices=("factorized", "full_cell", "factorized_plus_interactions"))
    args = parser.parse_args()
    resolution = resolve_experiment(args.experiment)
    config = resolution.resolved
    experiment_id = config["experiment_id"]
    run = resolve_run(args.run or experiment_id)
    unit = run / "kc" / "units" / args.cell_id / "input.json"
    opportunity = read_json(unit) if unit.is_file() else opportunity_from_run(args.cell_id, run)
    policies = [config["kc"]["policy"]]
    if args.compare_policy and args.compare_policy not in policies:
        policies.append(args.compare_policy)
    result = {
        "canonical_cell_id": args.cell_id,
        "opportunity": opportunity,
        "policies": {
            name: explain_policy(
                load_policy(repo_path(config["kc"]["policies"][name])), opportunity
            )
            for name in policies
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
