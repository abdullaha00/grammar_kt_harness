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
from .records import (
    compositional_base_event,
    compositional_projected_interaction,
    observable_base_event,
    projected_kt_interaction,
)
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

def prediction_metrics(
    targets: np.ndarray, predictions: np.ndarray, *, ece_bins: int = 10
) -> dict[str, Any]:
    if len(targets) == 0:
        return {
            "auc": None,
            "log_loss": None,
            "accuracy_at_0_5": None,
            "brier_score": None,
            "ece": None,
            "n": 0,
            "mean_prediction": None,
            "observed_rate": None,
        }
    predictions = np.clip(predictions, 1e-6, 1 - 1e-6)
    auc = float(roc_auc_score(targets, predictions)) if len(set(targets.tolist())) > 1 else None
    brier = float(np.mean((predictions - targets) ** 2))
    ece = 0.0
    boundaries = np.linspace(0.0, 1.0, ece_bins + 1)
    for index in range(ece_bins):
        if index == ece_bins - 1:
            mask = (predictions >= boundaries[index]) & (predictions <= boundaries[index + 1])
        else:
            mask = (predictions >= boundaries[index]) & (predictions < boundaries[index + 1])
        if np.any(mask):
            ece += float(np.mean(mask)) * abs(
                float(np.mean(predictions[mask])) - float(np.mean(targets[mask]))
            )
    return {
        "auc": auc,
        "log_loss": float(log_loss(targets, predictions, labels=[0, 1])),
        "brier_score": brier,
        "ece": ece,
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


# Phase-D development acquisition and frozen compositional probes

def project_compositional_interactions(
    acquisition_events: list[dict[str, Any]],
    probe_events: list[dict[str, Any]],
    item_projections: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    set[str],
    dict[str, Counter[str]],
]:
    """Annotate fixed Phase-D events without allowing probes to update history."""

    projection_by_item = {row["item_id"]: row for row in item_projections}
    if len(projection_by_item) != len(item_projections):
        raise RuntimeError("duplicate item-KC projections")
    event_item_ids = {row["item_id"] for row in acquisition_events + probe_events}
    if event_item_ids != set(projection_by_item):
        raise RuntimeError("Phase-D events and item-KC projection cover different item banks")
    development_supported = {
        kc_id
        for row in item_projections
        if row["canonical_split"] == "development"
        for kc_id in row["kc_ids"]
    }
    counts_by_learner: dict[str, Counter[str]] = defaultdict(Counter)
    projected_acquisition: list[dict[str, Any]] = []
    for base in sorted(
        acquisition_events, key=lambda row: (row["learner_id"], row["sequence_index"])
    ):
        compositional_base_event(base, label=base["event_id"])
        active = list(projection_by_item[base["item_id"]]["kc_ids"])
        supported = [kc_id for kc_id in active if kc_id in development_supported]
        cold = [kc_id for kc_id in active if kc_id not in development_supported]
        counts = counts_by_learner[base["learner_id"]]
        row = {
            **base,
            "kc_ids": active,
            "opportunity_indices": {kc_id: counts[kc_id] + 1 for kc_id in active},
            "development_supported_kc_ids": supported,
            "cold_kc_ids": cold,
            "covered": bool(active),
            "fully_development_supported": bool(active) and not cold,
        }
        compositional_projected_interaction(row, label=row["event_id"])
        projected_acquisition.append(row)
        counts.update(active)
    frozen_counts = {
        learner_id: Counter(counts) for learner_id, counts in counts_by_learner.items()
    }
    projected_probes: list[dict[str, Any]] = []
    for base in probe_events:
        compositional_base_event(base, label=base["event_id"])
        active = list(projection_by_item[base["item_id"]]["kc_ids"])
        supported = [kc_id for kc_id in active if kc_id in development_supported]
        cold = [kc_id for kc_id in active if kc_id not in development_supported]
        counts = frozen_counts[base["learner_id"]]
        row = {
            **base,
            "kc_ids": active,
            # All probes see the same next index; no probe increments it.
            "opportunity_indices": {kc_id: counts[kc_id] + 1 for kc_id in active},
            "development_supported_kc_ids": supported,
            "cold_kc_ids": cold,
            "covered": bool(active),
            "fully_development_supported": bool(active) and not cold,
        }
        compositional_projected_interaction(row, label=row["event_id"])
        projected_probes.append(row)
    return projected_acquisition, projected_probes, development_supported, frozen_counts


def frozen_development_statistics(
    acquisition_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Summarise observable development outcomes once, before any probe."""

    states: dict[str, dict[str, Any]] = {}
    for row in acquisition_rows:
        state = states.setdefault(
            row["learner_id"],
            {"attempts": 0, "correct": 0, "kc_attempts": Counter(), "kc_correct": Counter()},
        )
        state["attempts"] += 1
        state["correct"] += row["correct"]
        for kc_id in row["kc_ids"]:
            state["kc_attempts"][kc_id] += 1
            state["kc_correct"][kc_id] += row["correct"]
    return states


def frozen_probe_features(
    probe_rows: list[dict[str, Any]],
    kc_ids: list[str],
    states: dict[str, dict[str, Any]],
    *,
    alpha: float,
    beta: float,
    cold_prior: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    features, targets, empirical, global_fallback = [], [], [], []
    for row in probe_rows:
        state = states[row["learner_id"]]
        overall_rate = (state["correct"] + alpha) / (
            state["attempts"] + alpha + beta
        )
        rates = []
        for kc_id in row["kc_ids"]:
            if kc_id in row["cold_kc_ids"]:
                rates.append(cold_prior)
            else:
                rates.append(
                    (state["kc_correct"][kc_id] + alpha)
                    / (state["kc_attempts"][kc_id] + alpha + beta)
                )
        active_rate = sum(rates) / len(rates) if rates else overall_rate
        mean_log_opportunities = (
            sum(math.log1p(state["kc_attempts"][kc_id]) for kc_id in row["kc_ids"])
            / len(row["kc_ids"])
            if row["kc_ids"]
            else 0.0
        )
        vector = [
            overall_rate,
            active_rate,
            mean_log_opportunities,
            row["item_difficulty"],
            len(row["kc_ids"]),
        ]
        vector.extend(int(kc_id in row["kc_ids"]) for kc_id in kc_ids)
        features.append(vector)
        targets.append(row["correct"])
        empirical.append(active_rate)
        global_fallback.append(overall_rate)
    return (
        np.asarray(features, dtype=float),
        np.asarray(targets, dtype=int),
        np.asarray(empirical, dtype=float),
        np.asarray(global_fallback, dtype=float),
    )


def compositional_bkt_predictions(
    acquisition_rows: list[dict[str, Any]],
    probe_rows: list[dict[str, Any]],
    kc_ids: list[str],
    development_supported: set[str],
    *,
    learn: float,
    guess: float,
    slip: float,
    alpha: float,
    beta: float,
    cold_prior: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, dict[str, float]]]:
    """Update BKT on development only, then predict every probe from one snapshot."""

    train_success: Counter[str] = Counter()
    train_attempt: Counter[str] = Counter()
    for row in acquisition_rows:
        if row["dataset_split"] == "train":
            for kc_id in row["kc_ids"]:
                train_attempt[kc_id] += 1
                train_success[kc_id] += row["correct"]
    initial = {
        kc_id: (
            min(
                0.95,
                max(
                    0.05,
                    (train_success[kc_id] + alpha)
                    / (train_attempt[kc_id] + alpha + beta),
                ),
            )
            if train_attempt[kc_id]
            else cold_prior
        )
        for kc_id in kc_ids
    }
    by_learner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in acquisition_rows:
        by_learner[row["learner_id"]].append(row)
    acquisition_prediction_by_id: dict[str, float] = {}
    frozen_mastery: dict[str, dict[str, float]] = {}
    for learner_id, rows in by_learner.items():
        mastery = dict(initial)
        attempts = correct = 0
        for row in sorted(rows, key=lambda value: value["sequence_index"]):
            active = row["kc_ids"]
            global_prior = (correct + alpha) / (attempts + alpha + beta)
            if active:
                mean_mastery = sum(mastery[kc_id] for kc_id in active) / len(active)
                acquisition_prediction_by_id[row["event_id"]] = (
                    guess + (1.0 - slip - guess) * mean_mastery
                )
            else:
                acquisition_prediction_by_id[row["event_id"]] = global_prior
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
        frozen_mastery[learner_id] = mastery
    probe_predictions = []
    for row in probe_rows:
        state = frozen_mastery[row["learner_id"]]
        if not row["kc_ids"]:
            probe_predictions.append(float("nan"))
            continue
        mastery_values = [
            state[kc_id] if kc_id in development_supported else cold_prior
            for kc_id in row["kc_ids"]
        ]
        probe_predictions.append(
            guess + (1.0 - slip - guess) * sum(mastery_values) / len(mastery_values)
        )
    return (
        np.asarray(
            [acquisition_prediction_by_id[row["event_id"]] for row in acquisition_rows],
            dtype=float,
        ),
        np.asarray(probe_predictions, dtype=float),
        frozen_mastery,
    )


def representation_support_report(
    item_projections: list[dict[str, Any]],
    probe_rows: list[dict[str, Any]],
    development_supported: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    support_rows = []
    for row in sorted(
        (row for row in item_projections if row["canonical_split"] != "development"),
        key=lambda value: value["item_id"],
    ):
        supported = [kc_id for kc_id in row["kc_ids"] if kc_id in development_supported]
        cold = [kc_id for kc_id in row["kc_ids"] if kc_id not in development_supported]
        support_rows.append(
            {
                "item_id": row["item_id"],
                "canonical_cell_id": row["canonical_cell_id"],
                "canonical_split": row["canonical_split"],
                "kc_ids": row["kc_ids"],
                "development_supported_kc_ids": supported,
                "cold_kc_ids": cold,
                "covered": bool(row["kc_ids"]),
                "fully_development_supported": bool(row["kc_ids"]) and not cold,
            }
        )

    def summarize(split_name: str) -> dict[str, Any]:
        items = [row for row in support_rows if row["canonical_split"] == split_name]
        events = [row for row in probe_rows if row["canonical_split"] == split_name]
        active_assignments = sum(len(row["kc_ids"]) for row in events)
        reused_assignments = sum(
            len(row["development_supported_kc_ids"]) for row in events
        )
        cold_events = sum(bool(row["cold_kc_ids"]) for row in events)
        return {
            "items": len(items),
            "covered_items": sum(row["covered"] for row in items),
            "fully_development_supported_items": sum(
                row["fully_development_supported"] for row in items
            ),
            "item_coverage": sum(row["covered"] for row in items) / len(items)
            if items
            else None,
            "development_supported_item_coverage": sum(
                row["fully_development_supported"] for row in items
            )
            / len(items)
            if items
            else None,
            "events": len(events),
            "covered_events": sum(row["covered"] for row in events),
            "fully_development_supported_events": sum(
                row["fully_development_supported"] for row in events
            ),
            "event_coverage": sum(row["covered"] for row in events) / len(events)
            if events
            else None,
            "development_supported_event_coverage": sum(
                row["fully_development_supported"] for row in events
            )
            / len(events)
            if events
            else None,
            "cold_kc_event_rate": cold_events / len(events) if events else None,
            "component_reuse_rate": reused_assignments / active_assignments
            if active_assignments
            else None,
        }

    return (
        {
            "development_supported_kc_ids": sorted(development_supported),
            "definitions": {
                "covered": "one or more candidate KCs activate on the held-out item",
                "fully_development_supported": (
                    "all active candidate KCs had at least one development item opportunity"
                ),
                "cold": "an active KC had zero development item support",
                "uncovered": "the candidate policy assigns no KC",
            },
            "compositional_holdout": summarize("compositional_holdout"),
            "novel_feature_holdout": summarize("novel_feature_holdout"),
            "item_results": support_rows,
        },
        support_rows,
    )


def learner_bootstrap_log_loss_difference(
    predictions_a: list[dict[str, Any]],
    predictions_b: list[dict[str, Any]],
    *,
    technique: str,
    probe_type: str,
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    """Paired learner bootstrap of mean event log-loss difference A minus B."""

    rows_a = {
        row["event_id"]: row
        for row in predictions_a
        if row["probe_type"] == probe_type
    }
    rows_b = {
        row["event_id"]: row
        for row in predictions_b
        if row["probe_type"] == probe_type
    }
    if set(rows_a) != set(rows_b):
        raise ValueError("bootstrap predictions do not cover identical probe events")
    by_learner: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for event_id in sorted(rows_a):
        left, right = rows_a[event_id], rows_b[event_id]
        if (
            left["learner_id"] != right["learner_id"]
            or left["correct"] != right["correct"]
            or left["item_id"] != right["item_id"]
        ):
            raise ValueError("bootstrap inputs differ at the fixed-data boundary")
        target = left["correct"]
        pa = min(max(float(left[technique]), 1e-6), 1 - 1e-6)
        pb = min(max(float(right[technique]), 1e-6), 1 - 1e-6)
        loss_a = -(target * math.log(pa) + (1 - target) * math.log(1 - pa))
        loss_b = -(target * math.log(pb) + (1 - target) * math.log(1 - pb))
        by_learner[left["learner_id"]].append((loss_a, loss_b))
    learner_ids = sorted(by_learner)
    if not learner_ids:
        raise ValueError("bootstrap split contains no learners")
    observed_pairs = [pair for learner in learner_ids for pair in by_learner[learner]]
    observed = float(np.mean([left - right for left, right in observed_pairs]))
    rng = np.random.default_rng(seed)
    differences = []
    for _ in range(repetitions):
        sampled = rng.choice(learner_ids, size=len(learner_ids), replace=True)
        pairs = [pair for learner in sampled for pair in by_learner[str(learner)]]
        differences.append(float(np.mean([left - right for left, right in pairs])))
    lower, upper = (float(value) for value in np.quantile(differences, [0.025, 0.975]))
    direction = (
        "ontology_a_lower_log_loss"
        if upper < 0
        else "ontology_b_lower_log_loss"
        if lower > 0
        else "interval_includes_zero"
    )
    return {
        "estimand": "mean probe log loss, ontology A minus ontology B",
        "technique": technique,
        "probe_type": probe_type,
        "mean_difference": observed,
        "ci_95": [lower, upper],
        "learners": len(learner_ids),
        "events": len(observed_pairs),
        "bootstrap_repetitions": repetitions,
        "seed": seed,
        "direction": direction,
        "sampling_unit": "learner; all probe items retained for each sampled learner",
    }


def run_compositional_evaluation(
    run_dir: Path,
    output: Path,
    settings: dict[str, Any],
    technique_settings: dict[str, Any],
    techniques: list[str],
    item_projections: list[dict[str, Any]],
) -> dict[str, Any]:
    simulation_output = run_dir / "simulation" / "compositional"
    acquisition_events = read_jsonl(simulation_output / "acquisition_events.jsonl")
    comp_probes = read_jsonl(simulation_output / "compositional_probe_events.jsonl")
    novel_probes = read_jsonl(simulation_output / "novel_feature_probe_events.jsonl")
    fixed_probe_events = comp_probes + novel_probes
    acquisition, probes, development_supported, frozen_counts = (
        project_compositional_interactions(
            acquisition_events, fixed_probe_events, item_projections
        )
    )
    kc_ids = sorted({kc_id for row in item_projections for kc_id in row["kc_ids"]})
    if not kc_ids:
        raise RuntimeError("candidate ontology has no KCs on the fixed item bank")
    if not probes:
        compositional_output = output / "compositional"
        representation, _item_support_rows = representation_support_report(
            item_projections, probes, development_supported
        )
        write_jsonl(
            compositional_output / "acquisition_projected_interactions.jsonl",
            acquisition,
        )
        write_jsonl(compositional_output / "probe_projection.jsonl", [])
        write_jsonl(compositional_output / "development_predictions.jsonl", [])
        write_jsonl(compositional_output / "predictions.jsonl", [])
        write_jsonl(
            compositional_output / "learner_frozen_candidate_state.jsonl", []
        )
        write_json(compositional_output / "representation_support.json", representation)
        write_json(
            compositional_output / "model_details.json",
            {"status": "not_applicable_without_holdout_items", "oracle_fields_read": False},
        )
        write_json(
            compositional_output / "metrics.json",
            {"status": "not_applicable_without_holdout_items", "oracle_used_by_kt": False},
        )
        write_json(
            compositional_output / "bootstrap_comparisons.json",
            {"status": "not_applicable_without_holdout_items"},
        )
        return {
            "protocol_id": read_json(simulation_output / "audit.json")["protocol_id"],
            "acquisition_events": len(acquisition),
            "compositional_probe_events": 0,
            "novel_feature_probe_events": 0,
            "development_supported_kcs": len(development_supported),
            "all_probe_stream_sha256": read_json(simulation_output / "audit.json")[
                "all_probe_stream_sha256"
            ],
            "probe_state_updates": False,
            "oracle_input": False,
            "status": "not_applicable_without_holdout_items",
        }
    alpha = float(technique_settings["empirical"]["alpha"])
    beta = float(technique_settings["empirical"]["beta"])
    comp_settings = technique_settings["compositional"]
    cold_prior = float(comp_settings["cold_kc_prior"])
    ece_bins = int(comp_settings["ece_bins"])
    acquisition_features, acquisition_targets, acquisition_empirical, acquisition_global = (
        pre_event_features(acquisition, kc_ids, alpha, beta)
    )
    frozen_stats = frozen_development_statistics(acquisition)
    probe_features, probe_targets, probe_empirical, probe_global = frozen_probe_features(
        probes,
        kc_ids,
        frozen_stats,
        alpha=alpha,
        beta=beta,
        cold_prior=cold_prior,
    )
    acquisition_predictions: dict[str, np.ndarray] = {}
    probe_predictions: dict[str, np.ndarray] = {}
    bkt_frozen_mastery: dict[str, dict[str, float]] = {}
    logistic_metadata: dict[str, Any] | None = None
    if "empirical" in techniques:
        acquisition_predictions["empirical"] = acquisition_empirical
        probe_predictions["empirical"] = probe_empirical
    if "bkt" in techniques:
        bkt_settings = technique_settings["bkt"]
        acquisition_bkt, probe_bkt, bkt_frozen_mastery = compositional_bkt_predictions(
            acquisition,
            probes,
            kc_ids,
            development_supported,
            learn=float(bkt_settings["learn"]),
            guess=float(bkt_settings["guess"]),
            slip=float(bkt_settings["slip"]),
            alpha=alpha,
            beta=beta,
            cold_prior=cold_prior,
        )
        acquisition_predictions["bkt"] = acquisition_bkt
        probe_predictions["bkt"] = probe_bkt
    if "logistic" in techniques:
        logistic_settings = technique_settings["logistic"]
        model = LogisticRegression(
            C=float(logistic_settings["C"]),
            max_iter=int(logistic_settings["max_iter"]),
            solver=logistic_settings["solver"],
            random_state=int(logistic_settings["random_state"]),
        )
        acquisition_split = np.asarray([row["dataset_split"] for row in acquisition])
        model.fit(
            acquisition_features[acquisition_split == "train"],
            acquisition_targets[acquisition_split == "train"],
        )
        acquisition_predictions["logistic"] = model.predict_proba(acquisition_features)[:, 1]
        probe_predictions["logistic"] = model.predict_proba(probe_features)[:, 1]
        logistic_metadata = {
            "fit_partition": "development acquisition events with temporal split=train only",
            "intercept": float(model.intercept_[0]),
            "feature_order": [
                "prior_overall_rate",
                "prior_active_kc_rate",
                "mean_log_prior_opportunities",
                "item_difficulty",
                "kc_count",
                *kc_ids,
            ],
            "coefficients": [float(value) for value in model.coef_[0]],
        }
    acquisition_covered = np.asarray([row["covered"] for row in acquisition])
    probe_covered = np.asarray([row["covered"] for row in probes])
    for values in acquisition_predictions.values():
        values[~acquisition_covered] = acquisition_global[~acquisition_covered]
    for values in probe_predictions.values():
        values[~probe_covered] = probe_global[~probe_covered]

    representation, item_support_rows = representation_support_report(
        item_projections, probes, development_supported
    )
    acquisition_split = np.asarray([row["dataset_split"] for row in acquisition])
    probe_split = np.asarray([row["canonical_split"] for row in probes])
    probe_fully_supported = np.asarray(
        [row["fully_development_supported"] for row in probes]
    )
    metrics: dict[str, Any] = {
        "protocol_id": read_json(simulation_output / "audit.json")["protocol_id"],
        "purpose": (
            "transfer development-only learner evidence to unseen grammatical combinations "
            "under fixed controlled synthetic outcomes"
        ),
        "primary_metric": "log_loss",
        "oracle_used_by_kt": False,
        "probe_state_updates": False,
        "cold_kc_prior": cold_prior,
        "representation_support": {
            key: value
            for key, value in representation.items()
            if key != "item_results"
        },
        "development_evaluation": {},
        "holdout_evaluation": {},
    }
    for name in acquisition_predictions:
        metrics["development_evaluation"][name] = {
            "coverage": float(np.mean(acquisition_covered)),
            "development_supported_coverage": float(
                np.mean([row["fully_development_supported"] for row in acquisition])
            ),
            "cold_kc_rate": float(
                np.mean([bool(row["cold_kc_ids"]) for row in acquisition])
            ),
        }
        for temporal_split in ("validation", "test"):
            mask = acquisition_split == temporal_split
            metrics["development_evaluation"][name][temporal_split] = prediction_metrics(
                acquisition_targets[mask],
                acquisition_predictions[name][mask],
                ece_bins=ece_bins,
            )
        metrics["holdout_evaluation"][name] = {}
        for canonical_split in ("compositional_holdout", "novel_feature_holdout"):
            split_mask = probe_split == canonical_split
            support = representation[canonical_split]
            metrics["holdout_evaluation"][name][canonical_split] = {
                "coverage": support["event_coverage"],
                "development_supported_coverage": support[
                    "development_supported_event_coverage"
                ],
                "cold_kc_rate": support["cold_kc_event_rate"],
                "all_probes_fixed_fallback": prediction_metrics(
                    probe_targets[split_mask],
                    probe_predictions[name][split_mask],
                    ece_bins=ece_bins,
                ),
                "covered_probes": prediction_metrics(
                    probe_targets[split_mask & probe_covered],
                    probe_predictions[name][split_mask & probe_covered],
                    ece_bins=ece_bins,
                ),
                "fully_development_supported_probes": prediction_metrics(
                    probe_targets[split_mask & probe_fully_supported],
                    probe_predictions[name][split_mask & probe_fully_supported],
                    ece_bins=ece_bins,
                ),
            }
    acquisition_prediction_rows = [
        {
            "event_id": row["event_id"],
            "learner_id": row["learner_id"],
            "item_id": row["item_id"],
            "sequence_index": row["sequence_index"],
            "dataset_split": row["dataset_split"],
            "correct": row["correct"],
            **{
                name: float(values[index])
                for name, values in acquisition_predictions.items()
            },
        }
        for index, row in enumerate(acquisition)
    ]
    probe_prediction_rows = [
        {
            "event_id": row["event_id"],
            "learner_id": row["learner_id"],
            "item_id": row["item_id"],
            "canonical_cell_id": row["canonical_cell_id"],
            "canonical_split": row["canonical_split"],
            "probe_type": row["probe_type"],
            "correct": row["correct"],
            "covered": row["covered"],
            "fully_development_supported": row["fully_development_supported"],
            "cold_kc_ids": row["cold_kc_ids"],
            "fallback_usage": (
                "zero_kc_learner_global_development_prior"
                if not row["kc_ids"]
                else "cold_kc_fixed_prior"
                if row["cold_kc_ids"]
                else "none"
            ),
            **{name: float(values[index]) for name, values in probe_predictions.items()},
        }
        for index, row in enumerate(probes)
    ]
    frozen_state_rows = []
    for learner_id in sorted(frozen_stats):
        state = frozen_stats[learner_id]
        frozen_state_rows.append(
            {
                "learner_id": learner_id,
                "development_attempts": state["attempts"],
                "development_correct": state["correct"],
                "kc_attempts": dict(sorted(state["kc_attempts"].items())),
                "kc_correct": dict(sorted(state["kc_correct"].items())),
                "bkt_mastery": dict(sorted(bkt_frozen_mastery.get(learner_id, {}).items())),
                "probe_updates_applied": False,
            }
        )
    compositional_output = output / "compositional"
    write_jsonl(
        compositional_output / "acquisition_projected_interactions.jsonl", acquisition
    )
    write_jsonl(compositional_output / "probe_projection.jsonl", probes)
    write_jsonl(
        compositional_output / "development_predictions.jsonl",
        acquisition_prediction_rows,
    )
    write_jsonl(compositional_output / "predictions.jsonl", probe_prediction_rows)
    write_jsonl(
        compositional_output / "learner_frozen_candidate_state.jsonl", frozen_state_rows
    )
    write_json(compositional_output / "representation_support.json", representation)
    write_json(
        compositional_output / "model_details.json",
        {
            "development_supported_kc_ids": sorted(development_supported),
            "cold_kc_prior": cold_prior,
            "empirical_state_source": "all development acquisition outcomes only",
            "bkt_state_source": "all development acquisition outcomes only",
            "logistic_model": logistic_metadata,
            "probe_updates_applied": False,
            "oracle_fields_read": False,
        },
    )
    write_json(compositional_output / "metrics.json", metrics)
    write_json(
        compositional_output / "bootstrap_comparisons.json",
        {
            "status": "pairwise comparisons are computed by scripts/compare.py",
            "sampling_unit": "learner",
            "repetitions": int(comp_settings["bootstrap_repetitions"]),
            "seed": int(comp_settings["bootstrap_seed"]),
        },
    )
    simulation_audit = read_json(simulation_output / "audit.json")
    return {
        "protocol_id": metrics["protocol_id"],
        "acquisition_events": len(acquisition),
        "compositional_probe_events": len(comp_probes),
        "novel_feature_probe_events": len(novel_probes),
        "development_supported_kcs": len(development_supported),
        "all_probe_stream_sha256": simulation_audit["all_probe_stream_sha256"],
        "probe_state_updates": False,
        "oracle_input": False,
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
    compositional_summary = run_compositional_evaluation(
        run_dir,
        output,
        settings,
        technique_settings,
        techniques,
        item_projections,
    )
    return {
        "techniques": techniques,
        "rows": len(rows),
        "covered_rows": coverage["covered_events"],
        "uncovered_rows": coverage["uncovered_events"],
        "projected_interaction_sha256": event_stream_fingerprint(rows),
        "base_event_stream_sha256": simulation_audit["base_event_stream_sha256"],
        "oracle_input": False,
        "compositional": compositional_summary,
    }
