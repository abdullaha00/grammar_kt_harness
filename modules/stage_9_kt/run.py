"""Registry-driven technical KT baselines using pre-event observable features only."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score

from shared.utils.contracts import validate_jsonl
from shared.utils.io import ROOT, read_json, read_jsonl, repo_path, utc_now, write_json, write_jsonl
from shared.utils.manifests import write_stage_manifest
from shared.utils.research import prepare_stage_directory


def _metrics(targets: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    predictions = np.clip(predictions, 1e-6, 1 - 1e-6)
    return {
        "auc": float(roc_auc_score(targets, predictions)),
        "log_loss": float(log_loss(targets, predictions)),
        "accuracy_at_0_5": float(accuracy_score(targets, predictions >= 0.5)),
        "n": int(len(targets)),
        "mean_prediction": float(np.mean(predictions)),
        "observed_rate": float(np.mean(targets)),
    }


def _features(rows: list[dict[str, Any]], kc_ids: list[str], alpha: float, beta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    learner_attempts: Counter[str] = Counter()
    learner_correct: Counter[str] = Counter()
    learner_kc_attempts: Counter[tuple[str, str]] = Counter()
    learner_kc_correct: Counter[tuple[str, str]] = Counter()
    features = []
    targets = []
    empirical = []
    for row in rows:
        learner = row["learner_id"]
        active = row["kc_ids"]
        overall_rate = (learner_correct[learner] + alpha) / (learner_attempts[learner] + alpha + beta)
        kc_rates = [
            (learner_kc_correct[(learner, kc)] + alpha)
            / (learner_kc_attempts[(learner, kc)] + alpha + beta)
            for kc in active
        ]
        empirical.append(sum(kc_rates) / len(kc_rates))
        vector = [
            overall_rate,
            sum(kc_rates) / len(kc_rates),
            sum(math.log1p(row["opportunity_indices"][kc] - 1) for kc in active) / len(active),
            row["item_difficulty"],
            len(active),
        ]
        vector.extend(int(kc in active) for kc in kc_ids)
        features.append(vector)
        targets.append(row["correct"])
        learner_attempts[learner] += 1
        learner_correct[learner] += row["correct"]
        for kc in active:
            learner_kc_attempts[(learner, kc)] += 1
            learner_kc_correct[(learner, kc)] += row["correct"]
    return np.asarray(features, dtype=float), np.asarray(targets, dtype=int), np.asarray(empirical)


def _bkt(rows: list[dict[str, Any]], kc_ids: list[str], config: dict[str, float], alpha: float, beta: float) -> np.ndarray:
    train_success: Counter[str] = Counter()
    train_attempt: Counter[str] = Counter()
    for row in rows:
        if row["dataset_split"] == "train":
            for kc in row["kc_ids"]:
                train_attempt[kc] += 1
                train_success[kc] += row["correct"]
    initial = {
        kc: min(0.95, max(0.05, (train_success[kc] + alpha) / (train_attempt[kc] + alpha + beta)))
        for kc in kc_ids
    }
    predictions: dict[str, float] = {}
    by_learner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_learner[row["learner_id"]].append(row)
    guess = float(config["guess"])
    slip = float(config["slip"])
    learn = float(config["learn"])
    for learner_rows in by_learner.values():
        mastery = dict(initial)
        for row in sorted(learner_rows, key=lambda value: value["sequence_index"]):
            active = row["kc_ids"]
            mean_mastery = sum(mastery[kc] for kc in active) / len(active)
            predictions[row["event_id"]] = guess + (1.0 - slip - guess) * mean_mastery
            for kc in active:
                prior = mastery[kc]
                if row["correct"]:
                    posterior = prior * (1.0 - slip) / (prior * (1.0 - slip) + (1.0 - prior) * guess)
                else:
                    posterior = prior * slip / (prior * slip + (1.0 - prior) * (1.0 - guess))
                mastery[kc] = posterior + (1.0 - posterior) * learn
    return np.asarray([predictions[row["event_id"]] for row in rows])


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "kt"
    prepare_stage_directory(output)
    dataset_path = run_dir / "simulation" / "observable_interactions.jsonl"
    technique_config_path = repo_path(config["config"])
    interaction_schema = ROOT / "modules/stage_8_simulation/schemas/interaction.schema.json"
    validate_jsonl(dataset_path, interaction_schema, label="KT input Interaction")
    technique_config = read_json(technique_config_path)
    techniques = list(config["techniques"])
    allowed = {"empirical", "bkt", "logistic"}
    unknown = set(techniques) - allowed
    if unknown:
        raise ValueError(f"unknown KT techniques: {sorted(unknown)}")
    rows = read_jsonl(dataset_path)
    rows.sort(key=lambda row: (row["learner_id"], row["sequence_index"]))
    kc_ids = sorted({kc_id for row in rows for kc_id in row["kc_ids"]})
    alpha = float(technique_config["empirical"]["alpha"])
    beta = float(technique_config["empirical"]["beta"])
    features, targets, empirical = _features(rows, kc_ids, alpha, beta)
    split = np.asarray([row["dataset_split"] for row in rows])
    predictions: dict[str, np.ndarray] = {}
    extra: dict[str, Any] = {}
    if "empirical" in techniques:
        predictions["empirical"] = empirical
    if "bkt" in techniques:
        predictions["bkt"] = _bkt(rows, kc_ids, technique_config["bkt"], alpha, beta)
        extra["bkt_parameters"] = {
            **technique_config["bkt"],
            "initial_mastery_source": "smoothed train outcome rate per KC",
        }
    if "logistic" in techniques:
        logistic_config = technique_config["logistic"]
        model = LogisticRegression(
            C=float(logistic_config["C"]),
            max_iter=int(logistic_config["max_iter"]),
            solver=logistic_config["solver"],
            random_state=int(logistic_config["random_state"]),
        )
        model.fit(features[split == "train"], targets[split == "train"])
        predictions["logistic"] = model.predict_proba(features)[:, 1]
        extra["logistic_coefficients"] = {
            "intercept": float(model.intercept_[0]),
            "feature_order": [
                "prior_overall_rate", "prior_active_kc_rate", "mean_log_prior_opportunities",
                "item_difficulty", "kc_count", *kc_ids,
            ],
            "values": [float(value) for value in model.coef_[0]],
        }
    metrics: dict[str, Any] = {
        "purpose": "technical sanity only; not KC selection or cognitive validation",
        "oracle_used": False,
        "techniques": {},
        **extra,
    }
    for name, values in predictions.items():
        metrics["techniques"][name] = {
            current_split: _metrics(targets[split == current_split], values[split == current_split])
            for current_split in ("validation", "test")
        }
    prediction_rows = [
        {
            "event_id": row["event_id"],
            "learner_id": row["learner_id"],
            "sequence_index": row["sequence_index"],
            "dataset_split": row["dataset_split"],
            "correct": row["correct"],
            **{name: float(values[index]) for name, values in predictions.items()},
        }
        for index, row in enumerate(rows)
    ]
    predictions_path = output / "predictions.jsonl"
    metrics_path = output / "metrics.json"
    write_jsonl(predictions_path, prediction_rows)
    write_json(metrics_path, metrics)
    prediction_schema = ROOT / "modules/stage_9_kt/schemas/kt_prediction.schema.json"
    validate_jsonl(predictions_path, prediction_schema, label="KT output KTPrediction")
    write_stage_manifest(
        output,
        module="kt",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[dataset_path],
        configs=[experiment_manifest, technique_config_path, interaction_schema, prediction_schema],
        code=[Path(__file__)],
        outputs=[predictions_path, metrics_path],
        details={"techniques": techniques, "rows": len(rows), "oracle_input": False},
    )
