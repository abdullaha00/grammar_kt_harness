"""Technical KT baselines over candidate annotations of one fixed event stream."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score

from .io import read_json, read_jsonl, repo_path, write_json, write_jsonl
from .records import observable_base_event, projected_kt_interaction
from .simulation import event_stream_fingerprint


# Candidate annotation of fixed events

def project_interactions(
    base_events: list[dict[str, Any]], item_projections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Add candidate KCs and prior opportunity indices without changing an event."""

    projection_by_item = {row["item_id"]: row["kc_ids"] for row in item_projections}
    if len(projection_by_item) != len(item_projections):
        raise RuntimeError("duplicate item-KC projections")
    base_item_ids = {row["item_id"] for row in base_events}
    if set(projection_by_item) != base_item_ids:
        raise RuntimeError(
            "candidate projection does not exactly cover fixed-event items: "
            f"missing={sorted(base_item_ids - set(projection_by_item))}, "
            f"unused={sorted(set(projection_by_item) - base_item_ids)}"
        )
    if len({row["event_id"] for row in base_events}) != len(base_events):
        raise RuntimeError("fixed event stream contains duplicate event IDs")
    counts_by_learner: dict[str, Counter[str]] = defaultdict(Counter)
    projected = []
    for base in sorted(
        base_events, key=lambda row: (row["learner_id"], row["sequence_index"])
    ):
        observable_base_event(base, label=base["event_id"])
        active = list(projection_by_item[base["item_id"]])
        counts = counts_by_learner[base["learner_id"]]
        row = {
            **base,
            "kc_ids": active,
            "opportunity_indices": {kc_id: counts[kc_id] + 1 for kc_id in active},
        }
        projected_kt_interaction(row, label=row["event_id"])
        projected.append(row)
        counts.update(active)
    return projected


# Observable pre-event features and fixed zero-KC fallback

def pre_event_features(
    rows: list[dict[str, Any]], kc_ids: list[str], alpha: float, beta: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    learner_attempts: Counter[str] = Counter()
    learner_correct: Counter[str] = Counter()
    learner_kc_attempts: Counter[tuple[str, str]] = Counter()
    learner_kc_correct: Counter[tuple[str, str]] = Counter()
    features, targets, empirical, global_fallback = [], [], [], []
    for row in rows:
        learner = row["learner_id"]
        active = row["kc_ids"]
        overall_rate = (learner_correct[learner] + alpha) / (
            learner_attempts[learner] + alpha + beta
        )
        global_fallback.append(overall_rate)
        kc_rates = [
            (learner_kc_correct[(learner, kc_id)] + alpha)
            / (learner_kc_attempts[(learner, kc_id)] + alpha + beta)
            for kc_id in active
        ]
        active_rate = sum(kc_rates) / len(kc_rates) if active else overall_rate
        empirical.append(active_rate)
        mean_log_opportunities = (
            sum(
                math.log1p(row["opportunity_indices"][kc_id] - 1)
                for kc_id in active
            )
            / len(active)
            if active
            else 0.0
        )
        vector = [
            overall_rate,
            active_rate,
            mean_log_opportunities,
            row["item_difficulty"],
            len(active),
        ]
        vector.extend(int(kc_id in active) for kc_id in kc_ids)
        features.append(vector)
        targets.append(row["correct"])
        learner_attempts[learner] += 1
        learner_correct[learner] += row["correct"]
        for kc_id in active:
            learner_kc_attempts[(learner, kc_id)] += 1
            learner_kc_correct[(learner, kc_id)] += row["correct"]
    return (
        np.asarray(features, dtype=float),
        np.asarray(targets, dtype=int),
        np.asarray(empirical, dtype=float),
        np.asarray(global_fallback, dtype=float),
    )


def bkt_predictions(
    rows: list[dict[str, Any]],
    kc_ids: list[str],
    *,
    learn: float,
    guess: float,
    slip: float,
    alpha: float,
    beta: float,
) -> np.ndarray:
    train_success: Counter[str] = Counter()
    train_attempt: Counter[str] = Counter()
    for row in rows:
        if row["dataset_split"] == "train":
            for kc_id in row["kc_ids"]:
                train_attempt[kc_id] += 1
                train_success[kc_id] += row["correct"]
    initial = {
        kc_id: min(
            0.95,
            max(
                0.05,
                (train_success[kc_id] + alpha)
                / (train_attempt[kc_id] + alpha + beta),
            ),
        )
        for kc_id in kc_ids
    }
    predictions: dict[str, float] = {}
    by_learner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_learner[row["learner_id"]].append(row)
    for learner_rows in by_learner.values():
        mastery = dict(initial)
        attempts = correct = 0
        for row in sorted(learner_rows, key=lambda value: value["sequence_index"]):
            active = row["kc_ids"]
            global_prior = (correct + alpha) / (attempts + alpha + beta)
            if active:
                mean_mastery = sum(mastery[kc_id] for kc_id in active) / len(active)
                predictions[row["event_id"]] = guess + (1.0 - slip - guess) * mean_mastery
            else:
                predictions[row["event_id"]] = global_prior
            for kc_id in active:
                prior = mastery[kc_id]
                if row["correct"]:
                    posterior = prior * (1.0 - slip) / (
                        prior * (1.0 - slip) + (1.0 - prior) * guess
                    )
                else:
                    posterior = prior * slip / (
                        prior * slip + (1.0 - prior) * (1.0 - guess)
                    )
                mastery[kc_id] = posterior + (1.0 - posterior) * learn
            attempts += 1
            correct += row["correct"]
    return np.asarray([predictions[row["event_id"]] for row in rows])


# Evaluation

def prediction_metrics(targets: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    if len(targets) == 0:
        return {
            "auc": None,
            "log_loss": None,
            "accuracy_at_0_5": None,
            "n": 0,
            "mean_prediction": None,
            "observed_rate": None,
        }
    predictions = np.clip(predictions, 1e-6, 1 - 1e-6)
    auc = float(roc_auc_score(targets, predictions)) if len(set(targets.tolist())) > 1 else None
    return {
        "auc": auc,
        "log_loss": float(log_loss(targets, predictions, labels=[0, 1])),
        "accuracy_at_0_5": float(accuracy_score(targets, predictions >= 0.5)),
        "n": int(len(targets)),
        "mean_prediction": float(np.mean(predictions)),
        "observed_rate": float(np.mean(targets)),
    }


def coverage_report(
    rows: list[dict[str, Any]], item_projections: list[dict[str, Any]]
) -> dict[str, Any]:
    uncovered_items = sorted(row["item_id"] for row in item_projections if not row["kc_ids"])
    uncovered_set = set(uncovered_items)
    uncovered_events = [row for row in rows if row["item_id"] in uncovered_set]
    return {
        "items": len(item_projections),
        "covered_items": len(item_projections) - len(uncovered_items),
        "uncovered_items": len(uncovered_items),
        "uncovered_item_ids": uncovered_items,
        "item_coverage": round(
            (len(item_projections) - len(uncovered_items)) / len(item_projections), 6
        )
        if item_projections
        else 0.0,
        "events": len(rows),
        "covered_events": len(rows) - len(uncovered_events),
        "uncovered_events": len(uncovered_events),
        "event_coverage": round((len(rows) - len(uncovered_events)) / len(rows), 6)
        if rows
        else 0.0,
        "uncovered_events_by_temporal_split": dict(
            sorted(Counter(row["dataset_split"] for row in uncovered_events).items())
        ),
        "uncovered_events_by_canonical_split": dict(
            sorted(Counter(row["canonical_split"] for row in uncovered_events).items())
        ),
        "zero_kc_fallback": "learner-global smoothed pre-event empirical prior",
    }


# Full stage

def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "kt"
    output.mkdir(parents=True, exist_ok=False)
    base_events = read_jsonl(run_dir / "simulation" / "base_events.jsonl")
    item_projections = read_jsonl(run_dir / "kc" / "item_kc_projection.jsonl")
    rows = project_interactions(base_events, item_projections)

    technique_settings = read_json(repo_path(settings["parameters"]))
    techniques = list(settings["techniques"])
    allowed = {"empirical", "bkt", "logistic"}
    unknown = set(techniques) - allowed
    if unknown:
        raise ValueError(f"unknown KT techniques: {sorted(unknown)}")
    kc_ids = sorted({kc_id for row in rows for kc_id in row["kc_ids"]})
    if not kc_ids:
        raise RuntimeError("candidate ontology has no KCs on any accepted item")

    alpha = float(technique_settings["empirical"]["alpha"])
    beta = float(technique_settings["empirical"]["beta"])
    features, targets, empirical, global_fallback = pre_event_features(
        rows, kc_ids, alpha, beta
    )
    split = np.asarray([row["dataset_split"] for row in rows])
    covered = np.asarray([bool(row["kc_ids"]) for row in rows])
    predictions: dict[str, np.ndarray] = {}
    extra: dict[str, Any] = {}

    if "empirical" in techniques:
        predictions["empirical"] = empirical
    if "bkt" in techniques:
        bkt_settings = technique_settings["bkt"]
        predictions["bkt"] = bkt_predictions(
            rows,
            kc_ids,
            learn=float(bkt_settings["learn"]),
            guess=float(bkt_settings["guess"]),
            slip=float(bkt_settings["slip"]),
            alpha=alpha,
            beta=beta,
        )
        extra["bkt_parameters"] = {
            **technique_settings["bkt"],
            "initial_mastery_source": "smoothed train outcome rate per candidate KC",
        }
    if "logistic" in techniques:
        logistic_settings = technique_settings["logistic"]
        model = LogisticRegression(
            C=float(logistic_settings["C"]),
            max_iter=int(logistic_settings["max_iter"]),
            solver=logistic_settings["solver"],
            random_state=int(logistic_settings["random_state"]),
        )
        model.fit(features[split == "train"], targets[split == "train"])
        predictions["logistic"] = model.predict_proba(features)[:, 1]
        extra["logistic_coefficients"] = {
            "intercept": float(model.intercept_[0]),
            "feature_order": [
                "prior_overall_rate",
                "prior_active_kc_rate",
                "mean_log_prior_opportunities",
                "item_difficulty",
                "kc_count",
                *kc_ids,
            ],
            "values": [float(value) for value in model.coef_[0]],
        }

    # Every technique uses the same ontology-independent prediction on zero-KC events.
    for values in predictions.values():
        values[~covered] = global_fallback[~covered]

    coverage = coverage_report(rows, item_projections)
    simulation_audit = read_json(run_dir / "simulation" / "audit.json")
    metrics: dict[str, Any] = {
        "purpose": "fixed-data representation comparison; not cognitive KC validation",
        "oracle_used": False,
        "base_event_stream_sha256": simulation_audit["base_event_stream_sha256"],
        "coverage": coverage,
        "techniques": {},
        "temporal_split_warning": simulation_audit["temporal_split_warning"],
        **extra,
    }
    for name, values in predictions.items():
        metrics["techniques"][name] = {}
        for current_split in ("validation", "test"):
            all_mask = split == current_split
            covered_mask = all_mask & covered
            metrics["techniques"][name][current_split] = {
                "all_events_fixed_fallback": prediction_metrics(
                    targets[all_mask], values[all_mask]
                ),
                "covered_events": prediction_metrics(
                    targets[covered_mask], values[covered_mask]
                ),
            }

    prediction_rows = [
        {
            "event_id": row["event_id"],
            "learner_id": row["learner_id"],
            "sequence_index": row["sequence_index"],
            "dataset_split": row["dataset_split"],
            "canonical_split": row["canonical_split"],
            "correct": row["correct"],
            "covered_by_ontology": bool(row["kc_ids"]),
            "zero_kc_fallback_used": not row["kc_ids"],
            **{name: float(values[index]) for name, values in predictions.items()},
        }
        for index, row in enumerate(rows)
    ]
    write_jsonl(output / "projected_interactions.jsonl", rows)
    write_jsonl(output / "predictions.jsonl", prediction_rows)
    write_json(output / "metrics.json", metrics)
    return {
        "techniques": techniques,
        "rows": len(rows),
        "covered_rows": coverage["covered_events"],
        "uncovered_rows": coverage["uncovered_events"],
        "projected_interaction_sha256": event_stream_fingerprint(rows),
        "base_event_stream_sha256": simulation_audit["base_event_stream_sha256"],
        "oracle_input": False,
    }
