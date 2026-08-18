"""Print every auditable step for one normalization record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shared.utils.config import resolve_experiment
from shared.utils.io import read_json, read_jsonl, repo_path
from shared.utils.research import resolve_run


def _show(title: str, value: Any) -> None:
    print(f"\n== {title} ==")
    if isinstance(value, str):
        print(value.rstrip())
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def inspect_record(identifier: str, run_dir: Path, config: dict[str, Any]) -> None:
    units = read_jsonl(repo_path(config["source"]["annotation_units"]))
    unit = next(
        (
            row for row in units
            if row["duplicate_of"] is None and identifier in {row["egp_id"], row["unit_id"]}
        ),
        None,
    )
    if unit is None:
        raise KeyError(f"normalization unit not declared: {identifier}")
    root = run_dir / "normalization" / "units" / unit["unit_id"]
    phase1 = root / "phase1"
    if not phase1.is_dir():
        raise FileNotFoundError(f"normalization unit has not been run: {phase1}")
    phase1_input = read_json(phase1 / "input.json")
    _show("Source descriptor / exact Phase-1 input", phase1_input)
    _show("Rendered Phase-1 prompt", (phase1 / "rendered_prompt.txt").read_text(encoding="utf-8"))
    _show("Phase-1 invocation", read_json(phase1 / "invocation.json"))
    _show("Phase-1 raw output", (phase1 / "raw_output.txt").read_text(encoding="utf-8"))
    _show("Phase-1 parsed result", read_json(phase1 / "parsed_output.json"))
    _show("Phase-1 validator outcome", read_json(phase1 / "validation.json"))
    first = read_json(phase1 / "parsed_output.json")
    routed = first["result"] in {"partial", "unresolved"}
    run_one_result = read_json(root / "result.json") if (root / "result.json").is_file() else None
    _show(
        "Phase-2 routing",
        {
            "routed_by_contract": routed,
            "reason": (
                f"result={first['result']} is eligible for Phase 2"
                if routed else f"result={first['result']} is terminal"
            ),
            "phase2_evidence_present": (root / "phase2").is_dir(),
            "run_one_decision": (
                {
                    "phase2_routed": run_one_result["phase2_routed"],
                    "routing_reason": run_one_result["routing_reason"],
                }
                if run_one_result else None
            ),
        },
    )
    phase2 = root / "phase2"
    if phase2.is_dir():
        _show("Exact Phase-2 input", read_json(phase2 / "input.json"))
        _show("Rendered Phase-2 prompt", (phase2 / "rendered_prompt.txt").read_text(encoding="utf-8"))
        _show("Phase-2 invocation", read_json(phase2 / "invocation.json"))
        _show("Phase-2 raw output", (phase2 / "raw_output.txt").read_text(encoding="utf-8"))
        _show("Phase-2 parsed result", read_json(phase2 / "parsed_output.json"))
        _show("Phase-2 validator outcome", read_json(phase2 / "validation.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identifier", help="EGP ID or annotation unit ID")
    parser.add_argument("--experiment", default="current")
    parser.add_argument("--run", help="run ID/path; defaults to the experiment ID")
    args = parser.parse_args()
    resolution = resolve_experiment(args.experiment)
    run_dir = resolve_run(args.run or resolution.resolved["experiment_id"])
    inspect_record(args.identifier, run_dir, resolution.resolved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
