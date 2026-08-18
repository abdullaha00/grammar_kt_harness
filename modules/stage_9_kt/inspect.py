"""Inspect one prediction beside its observable pre-target input."""

from __future__ import annotations

import argparse
import json

from shared.utils.io import read_json, read_jsonl
from shared.utils.research import resolve_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_id")
    parser.add_argument("--experiment", default="current")
    parser.add_argument("--run")
    args = parser.parse_args()
    run = resolve_run(args.run or args.experiment)
    modern = (run / "simulation/observable_interactions.jsonl").is_file()
    interaction_path = run / (
        "simulation/observable_interactions.jsonl" if modern else "kt/datasets/v1/kt_dataset_v1.jsonl"
    )
    prediction_path = run / (
        "kt/predictions.jsonl" if modern else "kt/baselines/v0/predictions.jsonl"
    )
    interaction = next(
        row for row in read_jsonl(interaction_path)
        if row["event_id"] == args.event_id
    )
    prediction = next(
        row for row in read_jsonl(prediction_path)
        if row["event_id"] == args.event_id
    )
    if modern:
        manifest = read_json(run / "kt/manifest.json")
        techniques = manifest.get("details", {}).get("techniques")
        oracle_input = manifest.get("details", {}).get("oracle_input")
        stage_fingerprint = manifest.get("stage_fingerprint")
        metrics = read_json(run / "kt/metrics.json")
    else:
        manifest = read_json(run / "kt/datasets/v1/dataset_manifest.json")
        metrics = read_json(run / "kt/baselines/v0/results.json")
        techniques = sorted(metrics["models"])
        oracle_input = False
        stage_fingerprint = None
    print(
        json.dumps(
            {
                "evidence_layout": "research_harness" if modern else "legacy_accepted_reference_read_only",
                "observable_interaction": interaction,
                "prediction": prediction,
                "techniques": techniques,
                "oracle_input": oracle_input,
                "stage_fingerprint": stage_fingerprint,
                "dataset_record": manifest,
                "metrics": metrics,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
