#!/usr/bin/env python3
"""Re-select on retained Phase-3 events to calibrate the parsimony threshold."""

from __future__ import annotations

import copy
import gzip
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import read_yaml, write_json
from grammar_kt.kc_selection import score_candidate_policy, select_kcs


STUDY = ROOT / "reports/phase3/artifacts/selection_study_v1"
WORLD_IDS = (
    "phase3_factorized_v1",
    "phase3_perfect_negative_interaction_probe_v1",
)
SEEDS = tuple(range(20260827, 20260832))
INTERVENTIONS = (
    ("double_threshold_original", 0.002, 0.0001),
    ("objective_only_0.00025", 0.00025, 0.0),
    ("objective_only_0.0005", 0.0005, 0.0),
    ("objective_only_0.001", 0.001, 0.0),
)


def _read_gzip_jsonl(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _selected_ids(policy: dict[str, Any]) -> list[str]:
    return policy["selection_metadata"]["selected_candidate_ids"]


def main() -> None:
    inventory = json.loads(
        (STUDY / "candidate_inventory.json").read_text(encoding="utf-8")
    )
    base_design = read_yaml(ROOT / "modules/kcs/selection.yaml")
    base_ids = sorted(
        row["id"]
        for row in inventory["candidates"]
        if row["family"] == "feature_value" and row["selection_eligible"]
    )
    runs = []
    for world_id in WORLD_IDS:
        for seed in SEEDS:
            events = _read_gzip_jsonl(
                STUDY / "events" / f"{world_id}__seed_{seed}.jsonl.gz"
            )
            train_ids = {
                row["event_id"]
                for row in events
                if row["dataset_split"] == "train"
            }
            test_ids = {
                row["event_id"]
                for row in events
                if row["dataset_split"] == "test"
            }
            base_score, _predictions = score_candidate_policy(
                inventory,
                events,
                base_ids,
                base_design["selector_model"],
                train_ids,
                test_ids,
            )
            for label, penalty, minimum_improvement in INTERVENTIONS:
                design = copy.deepcopy(base_design)
                design["selection_id"] = f"phase3_{label}"
                design["objective"]["complexity_penalty"] = penalty
                design["objective"]["minimum_improvement"] = minimum_improvement
                policy = select_kcs(inventory, events, design)
                selected = _selected_ids(policy)
                selected_score, _predictions = score_candidate_policy(
                    inventory,
                    events,
                    selected,
                    design["selector_model"],
                    train_ids,
                    test_ids,
                )
                runs.append(
                    {
                        "world_id": world_id,
                        "seed": seed,
                        "intervention": label,
                        "complexity_penalty": penalty,
                        "minimum_improvement": minimum_improvement,
                        "selected_candidate_ids": selected,
                        "selected_addition_ids": sorted(set(selected) - set(base_ids)),
                        "validation": policy["selection_metadata"][
                            "final_validation_score"
                        ],
                        "reserved_test_log_loss": selected_score["log_loss"],
                        "reserved_test_minus_factorized_log_loss": (
                            selected_score["log_loss"] - base_score["log_loss"]
                        ),
                    }
                )

    summaries = []
    for world_id in WORLD_IDS:
        for label, penalty, minimum_improvement in INTERVENTIONS:
            selected_runs = [
                row
                for row in runs
                if row["world_id"] == world_id and row["intervention"] == label
            ]
            frequencies = Counter(
                candidate_id
                for row in selected_runs
                for candidate_id in row["selected_addition_ids"]
            )
            summaries.append(
                {
                    "world_id": world_id,
                    "intervention": label,
                    "complexity_penalty": penalty,
                    "minimum_improvement": minimum_improvement,
                    "addition_frequency_across_5_seeds": dict(
                        sorted(frequencies.items())
                    ),
                    "selected_kc_counts": [
                        len(row["selected_candidate_ids"]) for row in selected_runs
                    ],
                    "mean_reserved_test_minus_factorized_log_loss": mean(
                        row["reserved_test_minus_factorized_log_loss"]
                        for row in selected_runs
                    ),
                }
            )

    output = ROOT / "reports/phase3/artifacts/penalty_stability_v1"
    write_json(
        output / "results.json",
        {
            "experiment_id": "P3-KC-SELECTION-002",
            "source_event_study": str(STUDY.relative_to(ROOT)),
            "events_regenerated": False,
            "seeds": list(SEEDS),
            "interventions": [
                {
                    "id": label,
                    "complexity_penalty": penalty,
                    "minimum_improvement": minimum_improvement,
                }
                for label, penalty, minimum_improvement in INTERVENTIONS
            ],
            "summaries": summaries,
            "runs": runs,
        },
    )
    print(f"Wrote {output / 'results.json'}")


if __name__ == "__main__":
    main()
