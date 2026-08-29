"""Stage 10: explicit dataset, representation, and KT evaluation."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

from .validate_items import bank_summary


def _prediction_metrics(targets: np.ndarray, probabilities: np.ndarray, bins: int) -> dict[str, Any]:
    probabilities = np.clip(probabilities, 1e-6, 1 - 1e-6)
    if not len(targets):
        return {name: None for name in ("log_loss", "brier_score", "auc", "ece", "accuracy")} | {"n": 0}
    log_loss = float(np.mean(-(targets * np.log(probabilities) + (1 - targets) * np.log(1 - probabilities))))
    brier = float(np.mean((probabilities - targets) ** 2))
    auc = float(roc_auc_score(targets, probabilities)) if len(set(targets.tolist())) > 1 else None
    ece = 0.0
    edges = np.linspace(0, 1, bins + 1)
    for index in range(bins):
        mask = (probabilities >= edges[index]) & (
            probabilities <= edges[index + 1] if index == bins - 1 else probabilities < edges[index + 1]
        )
        if np.any(mask):
            ece += float(np.mean(mask)) * abs(float(np.mean(probabilities[mask])) - float(np.mean(targets[mask])))
    return {
        "n": len(targets),
        "log_loss": log_loss,
        "brier_score": brier,
        "auc": auc,
        "ece": ece,
        "accuracy": float(np.mean((probabilities >= 0.5) == targets)),
    }


def _representation_metrics(
    items: list[dict[str, Any]],
    events: list[dict[str, Any]],
    fold: list[dict[str, Any]],
    policy: dict[str, Any],
    projection: list[dict[str, Any]],
) -> dict[str, Any]:
    by_item = {row["item_id"]: row["kc_ids"] for row in projection}
    kc_ids = sorted({kc_id for values in by_item.values() for kc_id in values})
    supports = {kc_id: {item_id for item_id, values in by_item.items() if kc_id in values} for kc_id in kc_ids}
    redundant = []
    for index, left in enumerate(kc_ids):
        for right in kc_ids[index + 1 :]:
            if supports[left] == supports[right]:
                redundant.append([left, right])
    split_by_cell = {row["cell_id"]: row["grammar_split"] for row in fold}
    development_kcs = {
        kc_id
        for item in items
        if split_by_cell[item["cell_id"]] == "development"
        for kc_id in by_item[item["item_id"]]
    }
    compositional = [item for item in items if split_by_cell[item["cell_id"]] == "compositional_holdout"]
    compositional_covered = sum(
        bool(by_item[item["item_id"]]) and set(by_item[item["item_id"]]) <= development_kcs
        for item in compositional
    )
    assignments = sum(len(values) for values in by_item.values())
    covered_items = {item_id for item_id, values in by_item.items() if values}
    event_coverage = sum(event["item_id"] in covered_items for event in events) / len(events) if events else 0.0
    return {
        "policy_id": policy["policy_id"],
        "items": len(items),
        "kcs": len(kc_ids),
        "item_coverage": len(covered_items) / len(items) if items else 0.0,
        "event_coverage": event_coverage,
        "q_matrix_density": assignments / (len(items) * len(kc_ids)) if items and kc_ids else 0.0,
        "kcs_per_item": assignments / len(items) if items else 0.0,
        "kc_support": {kc_id: len(supports[kc_id]) for kc_id in kc_ids},
        "redundant_kcs": redundant,
        "compositional_coverage": compositional_covered / len(compositional) if compositional else None,
    }


def _bootstrap(
    test_events: list[dict[str, Any]],
    prediction_lookup: dict[tuple[str, str], float],
    techniques: list[str],
    policy: dict[str, Any],
) -> dict[str, Any]:
    if not policy["enabled"] or len(techniques) < 2 or not test_events:
        return {}
    rng = np.random.default_rng(policy["seed"])
    targets = np.asarray([event["correct"] for event in test_events])
    baseline = techniques[0]
    output = {}
    for technique in techniques[1:]:
        differences = []
        left = np.asarray([prediction_lookup[(event["event_id"], baseline)] for event in test_events])
        right = np.asarray([prediction_lookup[(event["event_id"], technique)] for event in test_events])
        for _ in range(policy["repeats"]):
            sample = rng.integers(0, len(test_events), len(test_events))
            left_loss = np.mean(-(targets[sample] * np.log(left[sample]) + (1 - targets[sample]) * np.log(1 - left[sample])))
            right_loss = np.mean(-(targets[sample] * np.log(right[sample]) + (1 - targets[sample]) * np.log(1 - right[sample])))
            differences.append(float(right_loss - left_loss))
        output[f"{technique}_minus_{baseline}_log_loss"] = {
            "mean": float(np.mean(differences)),
            "interval_95": [float(np.quantile(differences, 0.025)), float(np.quantile(differences, 0.975))],
        }
    return output


def paired_policy_bootstrap(
    events: list[dict[str, Any]],
    reference_predictions: list[dict[str, Any]],
    candidate_predictions: list[dict[str, Any]],
    *,
    repeats: int,
    seed: int,
    reference_policy_id: str = "reference",
    candidate_policy_id: str = "candidate",
) -> dict[str, Any]:
    """Paired learner-cluster bootstrap of candidate-minus-reference losses.

    ``events`` should already be restricted to the evaluation regime/split.
    Negative deltas favour the candidate KC policy. Whole learners are sampled
    with replacement and their events retain their natural event weighting.
    """

    if repeats < 1:
        raise ValueError("paired policy bootstrap repeats must be positive")
    if not events:
        return {
            "available": False,
            "reason": "no_evaluation_events",
            "reference_policy_id": reference_policy_id,
            "candidate_policy_id": candidate_policy_id,
            "sign_convention": "candidate_minus_reference; negative favours candidate",
            "sampling_unit": "learner",
            "aggregation": "event_weighted",
            "n_learners": 0,
            "n_events": 0,
            "repeats": repeats,
            "seed": seed,
        }

    ordered_events = sorted(
        events,
        key=lambda row: (
            str(row["learner_id"]),
            int(row.get("sequence_index", 0)),
            str(row["event_id"]),
        ),
    )
    event_ids = [row["event_id"] for row in ordered_events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("paired policy bootstrap event IDs must be unique")
    invalid_targets = [
        row["event_id"]
        for row in ordered_events
        if isinstance(row.get("correct"), bool)
        or row.get("correct") not in (0, 1)
    ]
    if invalid_targets:
        raise ValueError(
            "paired policy bootstrap outcomes must be binary 0/1: "
            f"{invalid_targets[:5]}"
        )

    def lookup(rows: list[dict[str, Any]], side: str) -> dict[str, float]:
        values: dict[str, float] = {}
        for row in rows:
            event_id = row["event_id"]
            if event_id in values:
                raise ValueError(f"{side} predictions contain duplicate event IDs")
            probability = float(row["probability"])
            if not np.isfinite(probability) or not 0.0 <= probability <= 1.0:
                raise ValueError(
                    f"{side} prediction probability must be finite and in [0, 1]: "
                    f"{event_id}={probability}"
                )
            values[event_id] = probability
        if set(values) != set(event_ids):
            raise ValueError(
                f"{side} predictions do not exactly cover evaluation events"
            )
        return {
            event_id: float(np.clip(probability, 1e-6, 1 - 1e-6))
            for event_id, probability in values.items()
        }

    reference = lookup(reference_predictions, "reference")
    candidate = lookup(candidate_predictions, "candidate")
    learner_ids = sorted({str(row["learner_id"]) for row in ordered_events})
    learner_index = {
        learner_id: index for index, learner_id in enumerate(learner_ids)
    }
    counts = np.zeros(len(learner_ids), dtype=float)
    delta_log_loss_sums = np.zeros(len(learner_ids), dtype=float)
    delta_brier_sums = np.zeros(len(learner_ids), dtype=float)
    reference_log_loss_sum = 0.0
    candidate_log_loss_sum = 0.0
    reference_brier_sum = 0.0
    candidate_brier_sum = 0.0
    for event in ordered_events:
        event_id = event["event_id"]
        target = float(event["correct"])
        reference_probability = reference[event_id]
        candidate_probability = candidate[event_id]
        reference_loss = -(
            target * np.log(reference_probability)
            + (1.0 - target) * np.log(1.0 - reference_probability)
        )
        candidate_loss = -(
            target * np.log(candidate_probability)
            + (1.0 - target) * np.log(1.0 - candidate_probability)
        )
        reference_brier = (reference_probability - target) ** 2
        candidate_brier = (candidate_probability - target) ** 2
        index = learner_index[str(event["learner_id"])]
        counts[index] += 1
        delta_log_loss_sums[index] += candidate_loss - reference_loss
        delta_brier_sums[index] += candidate_brier - reference_brier
        reference_log_loss_sum += reference_loss
        candidate_log_loss_sum += candidate_loss
        reference_brier_sum += reference_brier
        candidate_brier_sum += candidate_brier

    total_events = int(counts.sum())
    rng = np.random.default_rng(seed)
    sampled_indices = rng.integers(
        0,
        len(learner_ids),
        size=(repeats, len(learner_ids)),
        endpoint=False,
    )
    sampled_counts = counts[sampled_indices].sum(axis=1)
    sampled_log_loss = (
        delta_log_loss_sums[sampled_indices].sum(axis=1) / sampled_counts
    )
    sampled_brier = (
        delta_brier_sums[sampled_indices].sum(axis=1) / sampled_counts
    )

    def interval(values: np.ndarray) -> list[float] | None:
        if len(learner_ids) < 2:
            return None
        return [
            float(np.quantile(values, 0.025, method="linear")),
            float(np.quantile(values, 0.975, method="linear")),
        ]

    event_counts = sorted(int(value) for value in counts)

    return {
        "available": True,
        "reference_policy_id": reference_policy_id,
        "candidate_policy_id": candidate_policy_id,
        "sign_convention": "candidate_minus_reference; negative favours candidate",
        "sampling_unit": "learner",
        "aggregation": "event_weighted",
        "percentile_method": "linear",
        "n_learners": len(learner_ids),
        "n_events": total_events,
        "events_per_learner": {
            "minimum": event_counts[0],
            "median": float(np.median(event_counts)),
            "maximum": event_counts[-1],
        },
        "repeats": repeats,
        "seed": seed,
        "observed": {
            "reference": {
                "log_loss": float(reference_log_loss_sum / total_events),
                "brier_score": float(reference_brier_sum / total_events),
            },
            "candidate": {
                "log_loss": float(candidate_log_loss_sum / total_events),
                "brier_score": float(candidate_brier_sum / total_events),
            },
        },
        "delta_log_loss": {
            "point_estimate": float(delta_log_loss_sums.sum() / total_events),
            "interval_95": interval(sampled_log_loss),
        },
        "delta_brier_score": {
            "point_estimate": float(delta_brier_sums.sum() / total_events),
            "interval_95": interval(sampled_brier),
        },
    }


def evaluate(
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    accepted_items: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    fold: list[dict[str, Any]],
    events: list[dict[str, Any]],
    policy: dict[str, Any],
    projection: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    protocol: dict[str, Any],
    *,
    validator_accepted_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    dataset = bank_summary(
        candidates,
        (
            accepted_items
            if validator_accepted_items is None
            else validator_accepted_items
        ),
        judgments,
        cells,
        selected_items=accepted_items,
    )
    dataset["grammar_cell_coverage"] = (
        dataset["covered_cells"] / dataset["grammar_cells"] if dataset["grammar_cells"] else 0.0
    )
    representation = _representation_metrics(accepted_items, events, fold, policy, projection)
    lookup = {(row["event_id"], row["technique"]): row["probability"] for row in predictions}
    techniques = list(dict.fromkeys(row["technique"] for row in predictions))
    kt_results = {}
    for technique in techniques:
        selected = [event for event in events if event["dataset_split"] == "test"]
        targets = np.asarray([event["correct"] for event in selected])
        probabilities = np.asarray([lookup[(event["event_id"], technique)] for event in selected])
        result = _prediction_metrics(targets, probabilities, protocol["ece_bins"])
        result["grammar_split_metrics"] = {}
        for split in ("development", "compositional_holdout", "novel_feature_holdout"):
            split_events = [event for event in selected if event["grammar_split"] == split]
            split_targets = np.asarray([event["correct"] for event in split_events])
            split_probabilities = np.asarray([lookup[(event["event_id"], technique)] for event in split_events])
            result["grammar_split_metrics"][split] = _prediction_metrics(
                split_targets, split_probabilities, protocol["ece_bins"]
            )
        kt_results[technique] = result
    test_events = [event for event in events if event["dataset_split"] == "test"]
    return {
        "protocol_id": protocol["protocol_id"],
        "dataset": dataset,
        "representation": representation,
        "kt": kt_results,
        "paired_bootstrap": _bootstrap(test_events, lookup, techniques, protocol["paired_bootstrap"]),
        "input_counts": {
            "events": len(events),
            "predictions": len(predictions),
            "prediction_events": len({row["event_id"] for row in predictions}),
        },
    }
