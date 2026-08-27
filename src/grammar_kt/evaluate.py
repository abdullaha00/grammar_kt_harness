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
) -> dict[str, Any]:
    dataset = bank_summary(candidates, accepted_items, judgments, cells)
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
