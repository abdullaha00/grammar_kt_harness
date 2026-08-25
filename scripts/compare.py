#!/usr/bin/env python3
"""Compare two runs at the five scientific module boundaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt.io import read_json
from grammar_kt.runner import STAGE_NAMES


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_a", type=Path)
    parser.add_argument("run_b", type=Path)
    args = parser.parse_args()
    left = read_json(args.run_a / "metadata.json")
    right = read_json(args.run_b / "metadata.json")
    comparisons = {}
    for stage in STAGE_NAMES:
        left_stage = left.get("stages", {}).get(stage, {})
        right_stage = right.get("stages", {}).get(stage, {})
        comparisons[stage] = {
            "same_input_signature": (
                left.get("stage_input_signatures", {}).get(stage, {}).get("sha256")
                == right.get("stage_input_signatures", {}).get(stage, {}).get("sha256")
            ),
            "same_summary": left_stage.get("summary") == right_stage.get("summary"),
            "run_a": left_stage.get("summary"),
            "run_b": right_stage.get("summary"),
        }
    report = {
        "run_a": str(args.run_a),
        "run_b": str(args.run_b),
        "generator_a": left.get("generator"),
        "generator_b": right.get("generator"),
        "stages": comparisons,
        "interpretation_boundary": "differences are descriptive; this script does not select a scientific condition",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
