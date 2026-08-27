"""Stage 9: three deliberately simple KT baselines on the same event stream."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from .io import read_yaml


def history_features(
    events: list[dict[str, Any]], projection: list[dict[str, Any]], alpha: float, beta: float
) -> tuple[list[dict[str, Any]], list[str]]:
    """Build observable features, updating counts only after each event's row."""

    by_item = {row["item_id"]: row["kc_ids"] for row in projection}
    event_items = {row["item_id"] for row in events}
    if event_items - set(by_item):
        raise ValueError(f"KC projection lacks event items: {sorted(event_items - set(by_item))}")
    kc_ids = sorted({kc_id for values in by_item.values() for kc_id in values})
    learner_attempts: Counter[str] = Counter()
    learner_correct: Counter[str] = Counter()
    kc_attempts: Counter[tuple[str, str]] = Counter()
    kc_correct: Counter[tuple[str, str]] = Counter()
    rows_by_event = {}

    for event in sorted(events, key=lambda row: (row["learner_id"], row["sequence_index"])):
        learner = event["learner_id"]
        active = by_item[event["item_id"]]
        overall = (learner_correct[learner] + alpha) / (learner_attempts[learner] + alpha + beta)
        rates = [
            (kc_correct[(learner, kc_id)] + alpha) / (kc_attempts[(learner, kc_id)] + alpha + beta)
            for kc_id in active
        ]
        active_rate = sum(rates) / len(rates) if rates else overall
        mean_log_attempts = (
            sum(math.log1p(kc_attempts[(learner, kc_id)]) for kc_id in active) / len(active)
            if active
            else 0.0
        )
        vector = [overall, active_rate, mean_log_attempts, event["item_difficulty"], len(active)]
        vector.extend(int(kc_id in active) for kc_id in kc_ids)
        rows_by_event[event["event_id"]] = {
            "event_id": event["event_id"],
            "vector": vector,
            "empirical_probability": active_rate,
            "history_events": learner_attempts[learner],
        }
        learner_attempts[learner] += 1
        learner_correct[learner] += event["correct"]
        for kc_id in active:
            kc_attempts[(learner, kc_id)] += 1
            kc_correct[(learner, kc_id)] += event["correct"]
    return [rows_by_event[event["event_id"]] for event in events], kc_ids


def _bkt(
    events: list[dict[str, Any]], projection: list[dict[str, Any]], parameters: dict[str, float]
) -> dict[str, float]:
    by_item = {row["item_id"]: row["kc_ids"] for row in projection}
    kc_ids = sorted({kc_id for values in by_item.values() for kc_id in values})
    state: dict[str, dict[str, float]] = defaultdict(
        lambda: {kc_id: parameters["initial_mastery"] for kc_id in kc_ids}
    )
    learner_attempts: Counter[str] = Counter()
    learner_correct: Counter[str] = Counter()
    predictions = {}
    for event in sorted(events, key=lambda row: (row["learner_id"], row["sequence_index"])):
        learner = event["learner_id"]
        active = by_item[event["item_id"]]
        if active:
            mean_mastery = sum(state[learner][kc_id] for kc_id in active) / len(active)
            probability = parameters["guess"] + (
                1.0 - parameters["slip"] - parameters["guess"]
            ) * mean_mastery
        else:
            probability = (learner_correct[learner] + 1) / (learner_attempts[learner] + 2)
        predictions[event["event_id"]] = probability
        for kc_id in active:
            prior = state[learner][kc_id]
            if event["correct"]:
                posterior = prior * (1 - parameters["slip"]) / (
                    prior * (1 - parameters["slip"]) + (1 - prior) * parameters["guess"]
                )
            else:
                posterior = prior * parameters["slip"] / (
                    prior * parameters["slip"] + (1 - prior) * (1 - parameters["guess"])
                )
            state[learner][kc_id] = posterior + (1 - posterior) * parameters["learn"]
        learner_attempts[learner] += 1
        learner_correct[learner] += event["correct"]
    return predictions


def run_kt(
    events: list[dict[str, Any]], projection: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    protocol = read_yaml(config["protocol"])
    empirical = protocol["empirical"]
    features, _kc_ids = history_features(events, projection, empirical["alpha"], empirical["beta"])
    feature_by_event = {row["event_id"]: row for row in features}
    predictions_by_technique: dict[str, dict[str, float]] = {}

    if "empirical" in protocol["techniques"]:
        predictions_by_technique["empirical"] = {
            row["event_id"]: row["empirical_probability"] for row in features
        }
    if "bkt" in protocol["techniques"]:
        predictions_by_technique["bkt"] = _bkt(events, projection, protocol["bkt"])
    if "logistic" in protocol["techniques"]:
        x = np.asarray([row["vector"] for row in features], dtype=float)
        y = np.asarray([event["correct"] for event in events], dtype=int)
        train = np.asarray([event["dataset_split"] == "train" for event in events])
        if len(set(y[train].tolist())) < 2:
            probabilities = np.asarray([row["empirical_probability"] for row in features])
        else:
            parameters = protocol["logistic"]
            model = LogisticRegression(
                C=parameters["regularization_c"],
                max_iter=parameters["max_iterations"],
                random_state=parameters["random_seed"],
            )
            model.fit(x[train], y[train])
            probabilities = model.predict_proba(x)[:, 1]
        predictions_by_technique["logistic"] = {
            event["event_id"]: float(probability)
            for event, probability in zip(events, probabilities, strict=True)
        }

    rows = []
    for technique in protocol["techniques"]:
        for event in events:
            probability = predictions_by_technique[technique][event["event_id"]]
            rows.append(
                {
                    "event_id": event["event_id"],
                    "technique": technique,
                    "probability": float(min(1 - 1e-6, max(1e-6, probability))),
                    "history_events": feature_by_event[event["event_id"]]["history_events"],
                }
            )
    return rows
