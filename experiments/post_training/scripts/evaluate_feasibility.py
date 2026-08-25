#!/usr/bin/env python3
"""Evaluate deterministic validity, coverage, leakage, and shortcut risk."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline

from grammar_kt.io import ROOT, read_json, read_jsonl, write_json


def grouped_shortcut_accuracy(
    preferences: list[dict[str, Any]], *, folds: int, seed: int
) -> dict[str, Any]:
    texts: list[str] = []
    labels: list[int] = []
    groups: list[str] = []
    for row in preferences:
        group = row["hidden_generation_metadata"]["nuisance_group_id"]
        texts.extend((row["chosen"], row["rejected"]))
        labels.extend((1, 0))
        groups.extend((group, group))
    unique_groups = sorted(set(groups))
    selected_folds = min(folds, len(unique_groups))
    splitter = GroupKFold(n_splits=selected_folds)
    fold_rows = []
    predictions = np.zeros(len(labels), dtype=int)
    for fold, (train, test) in enumerate(
        splitter.split(texts, labels, groups=groups), 1
    ):
        model = make_pipeline(
            TfidfVectorizer(analyzer="char", ngram_range=(2, 5), min_df=2),
            LogisticRegression(max_iter=1000, random_state=seed),
        )
        train_text = [texts[index] for index in train]
        test_text = [texts[index] for index in test]
        train_labels = np.asarray(labels)[train]
        model.fit(train_text, train_labels)
        fold_predictions = model.predict(test_text)
        predictions[test] = fold_predictions
        fold_rows.append(
            {
                "fold": fold,
                "train_nuisance_groups": sorted({groups[index] for index in train}),
                "test_nuisance_groups": sorted({groups[index] for index in test}),
                "test_candidates": len(test),
                "accuracy": float(accuracy_score(np.asarray(labels)[test], fold_predictions)),
            }
        )
    return {
        "method": "response-only char(2,5) TF-IDF + logistic regression",
        "split": "GroupKFold by complete realization nuisance signature",
        "folds": fold_rows,
        "accuracy": float(accuracy_score(labels, predictions)),
        "chance_accuracy": 0.5,
        "interpretation": "High accuracy would reveal a context-free chosen/rejected surface shortcut; it is not a measure of LLM tutoring quality.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "experiments/post_training/configs/feasibility_v0.json",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=ROOT / "experiments/post_training/data/feasibility_v0",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments/post_training/results/feasibility_v0",
    )
    args = parser.parse_args()
    config = read_json(args.config)
    preferences = read_jsonl(args.data / "preference.jsonl")
    sft = read_jsonl(args.data / "sft.jsonl")
    verifier = read_jsonl(args.data / "verifier.jsonl")
    dialogue = read_jsonl(args.data / "dialogue.jsonl")
    trajectories = read_jsonl(args.data / "trajectory.jsonl")

    dimensions = Counter(
        row["preference_label"]["differing_dimension"] for row in preferences
    )
    splits = Counter(row["data_split"] for row in preferences)
    chosen_by_text: dict[str, int] = Counter(row["chosen"] for row in preferences)
    rejected_by_text: dict[str, int] = Counter(row["rejected"] for row in preferences)
    all_texts = set(chosen_by_text) | set(rejected_by_text)
    both_roles = [
        text for text in all_texts if chosen_by_text[text] and rejected_by_text[text]
    ]
    reverse_keys = {(row["chosen"], row["rejected"]) for row in preferences}
    deterministic_valid = [
        row["preference_label"]["chosen_exact_target"] is True
        and row["preference_label"]["rejected_exact_target"] is False
        and row["preference_label"]["rejected_is_valid_for_alternative_cell"] is True
        and row["preference_label"]["same_realization_nuisance_signature"] is True
        and row["preference_label"]["hamming_distance"] == 1
        and row["chosen"] != row["rejected"]
        for row in preferences
    ]
    shortcut = grouped_shortcut_accuracy(
        preferences,
        folds=int(config["shortcut_evaluation_folds"]),
        seed=int(config["seed"]),
    )
    criteria = config["decision_criteria"]
    decisions = {
        "minimum_pair_count": len(preferences)
        >= int(criteria["minimum_preference_pairs"]),
        "minimum_dimension_support": bool(dimensions)
        and min(dimensions.values())
        >= int(criteria["minimum_pairs_per_observed_error_dimension"]),
        "deterministic_pair_validity": (
            sum(deterministic_valid) / len(deterministic_valid)
        )
        >= float(criteria["required_deterministic_pair_validity"]),
        "response_only_shortcut_below_threshold": shortcut["accuracy"]
        <= float(criteria["maximum_response_only_shortcut_accuracy"]),
    }
    summary = {
        "experiment_id": config["experiment_id"],
        "counts": {
            "sft": len(sft),
            "preference": len(preferences),
            "verifier": len(verifier),
            "dialogue": len(dialogue),
            "trajectory": len(trajectories),
        },
        "sft_tasks": dict(sorted(Counter(row["task"] for row in sft).items())),
        "preference_dimensions": dict(sorted(dimensions.items())),
        "preference_splits": dict(sorted(splits.items())),
        "preference_contexts": len(
            {
                json.dumps(row["context"], sort_keys=True)
                for row in preferences
            }
        ),
        "unique_candidate_sentences": len(all_texts),
        "candidate_sentences_seen_in_both_roles": len(both_roles),
        "all_pairs_have_reverse_orientation": all(
            (right, left) in reverse_keys for left, right in reverse_keys
        ),
        "deterministic_valid_pairs": sum(deterministic_valid),
        "deterministic_pair_validity_rate": sum(deterministic_valid)
        / len(deterministic_valid),
        "response_only_shortcut": shortcut,
        "decision_criteria": decisions,
        "overall_feasibility_gate": all(decisions.values()),
        "leakage_warning": "Train only on records whose complete provenance chain is development. A pair involving a held-out target or rejected cell is evaluation-only.",
        "trajectory_warning": "Trajectory actions came from shuffled simulator passes and have no optimal-action label; they are schema examples, not policy demonstrations.",
        "dialogue_warning": "Dialogue responses are weak templates with no human pedagogical validation.",
        "exact_command": ".venv/bin/python experiments/post_training/scripts/evaluate_feasibility.py",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "summary.json", summary)
    examples = {
        "sft": sft[:2],
        "preference": preferences[:2],
        "verifier": verifier[:2],
        "dialogue": dialogue[:2],
        "trajectory": trajectories[:2],
    }
    write_json(args.output / "representative_examples.json", examples)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["overall_feasibility_gate"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
