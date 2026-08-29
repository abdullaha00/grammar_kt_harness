"""Development-only predictive/parsimony selection of a frozen KC policy."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


def _candidate_lookup(candidate_inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = candidate_inventory["candidates"]
    by_id = {row["id"]: row for row in candidates}
    if len(by_id) != len(candidates):
        raise ValueError("candidate inventory contains duplicate IDs")
    return by_id


def _development_projection(
    candidate_inventory: dict[str, Any], candidate_ids: list[str]
) -> dict[str, list[str]]:
    by_id = _candidate_lookup(candidate_inventory)
    unknown = set(candidate_ids) - set(by_id)
    if unknown:
        raise ValueError(f"unknown candidate IDs: {sorted(unknown)}")
    item_ids = candidate_inventory["development_item_ids"]
    projection = {item_id: [] for item_id in item_ids}
    for candidate_id in candidate_ids:
        for item_id in by_id[candidate_id]["supporting_development_item_ids"]:
            if item_id not in projection:
                raise ValueError(
                    f"candidate support includes non-development item: {item_id}"
                )
            projection[item_id].append(candidate_id)
    return {
        item_id: sorted(values) for item_id, values in sorted(projection.items())
    }


def _history_vectors(
    events: list[dict[str, Any]],
    projection: dict[str, list[str]],
    candidate_ids: list[str],
    model_design: dict[str, Any],
) -> list[dict[str, Any]]:
    alpha = float(model_design["history_prior"]["alpha"])
    beta = float(model_design["history_prior"]["beta"])
    if alpha <= 0 or beta <= 0:
        raise ValueError("history prior parameters must be positive")
    expected_features = [
        "learner_success_rate",
        "learner_log_attempts",
        "per_kc_active",
        "per_kc_prior_successes",
        "per_kc_prior_failures",
    ]
    if model_design.get("features") != expected_features:
        raise ValueError(
            "observable selector uses the declared fixed-width feature set: "
            f"{expected_features}"
        )
    learner_attempts: Counter[str] = Counter()
    learner_correct: Counter[str] = Counter()
    kc_attempts: Counter[tuple[str, str]] = Counter()
    kc_correct: Counter[tuple[str, str]] = Counter()
    rows_by_event: dict[str, dict[str, Any]] = {}

    for event in sorted(
        events, key=lambda row: (row["learner_id"], row["sequence_index"])
    ):
        learner_id = event["learner_id"]
        if event["item_id"] not in projection:
            raise ValueError(
                f"selector received a non-development item: {event['item_id']}"
            )
        active = set(projection[event["item_id"]])
        overall_rate = (learner_correct[learner_id] + alpha) / (
            learner_attempts[learner_id] + alpha + beta
        )
        vector = [overall_rate, math.log1p(learner_attempts[learner_id])]
        for candidate_id in candidate_ids:
            if candidate_id in active:
                attempts = kc_attempts[(learner_id, candidate_id)]
                successes = kc_correct[(learner_id, candidate_id)]
                vector.extend([1.0, float(successes), float(attempts - successes)])
            else:
                vector.extend([0.0, 0.0, 0.0])
        rows_by_event[event["event_id"]] = {
            "event_id": event["event_id"],
            "vector": vector,
            "history_events": learner_attempts[learner_id],
        }
        learner_attempts[learner_id] += 1
        learner_correct[learner_id] += int(event["correct"])
        for candidate_id in active:
            kc_attempts[(learner_id, candidate_id)] += 1
            kc_correct[(learner_id, candidate_id)] += int(event["correct"])
    return [rows_by_event[event["event_id"]] for event in events]


def fit_predict_kc_logistic(
    candidate_inventory: dict[str, Any],
    events: list[dict[str, Any]],
    candidate_ids: list[str],
    model_design: dict[str, Any],
    train_event_ids: set[str],
) -> list[dict[str, Any]]:
    """Fit on declared events and predict every row from strictly prior history."""

    candidate_ids = sorted(candidate_ids)
    projection = _development_projection(candidate_inventory, candidate_ids)
    vectors = _history_vectors(events, projection, candidate_ids, model_design)
    vector_by_event = {row["event_id"]: row for row in vectors}
    event_ids = {row["event_id"] for row in events}
    unknown_train = train_event_ids - event_ids
    if unknown_train:
        raise ValueError(f"unknown selector training events: {sorted(unknown_train)}")
    train_events = [row for row in events if row["event_id"] in train_event_ids]
    if not train_events:
        raise ValueError("selector model has no training events")
    train_targets = np.asarray([row["correct"] for row in train_events], dtype=int)
    if len(set(train_targets.tolist())) < 2:
        raise ValueError("selector model training outcomes need both classes")
    train_x = np.asarray(
        [vector_by_event[row["event_id"]]["vector"] for row in train_events],
        dtype=float,
    )
    all_x = np.asarray(
        [vector_by_event[row["event_id"]]["vector"] for row in events], dtype=float
    )
    scaler = StandardScaler()
    train_x = scaler.fit_transform(train_x)
    all_x = scaler.transform(all_x)
    model = LogisticRegression(
        C=float(model_design["regularization_c"]),
        max_iter=int(model_design["max_iterations"]),
        random_state=int(model_design["random_seed"]),
    )
    model.fit(train_x, train_targets)
    probabilities = model.predict_proba(all_x)[:, 1]
    return [
        {
            "event_id": event["event_id"],
            "probability": float(min(1 - 1e-6, max(1e-6, probability))),
            "history_events": vector_by_event[event["event_id"]]["history_events"],
        }
        for event, probability in zip(events, probabilities, strict=True)
    ]


def predict_kc_bkt(
    candidate_inventory: dict[str, Any],
    events: list[dict[str, Any]],
    candidate_ids: list[str],
    model_design: dict[str, Any],
) -> list[dict[str, Any]]:
    """Apply the fixed multi-KC BKT control with strictly online updates."""

    candidate_ids = sorted(candidate_ids)
    projection = _development_projection(candidate_inventory, candidate_ids)
    initial = float(model_design["initial_mastery"])
    learn = float(model_design["learn"])
    guess = float(model_design["guess"])
    slip = float(model_design["slip"])
    state: dict[str, dict[str, float]] = defaultdict(
        lambda: {candidate_id: initial for candidate_id in candidate_ids}
    )
    learner_attempts: Counter[str] = Counter()
    learner_correct: Counter[str] = Counter()
    predictions_by_event = {}
    history_by_event = {}
    for event in sorted(
        events, key=lambda row: (row["learner_id"], row["sequence_index"])
    ):
        learner_id = event["learner_id"]
        if event["item_id"] not in projection:
            raise ValueError(
                f"selector received a non-development item: {event['item_id']}"
            )
        active = projection[event["item_id"]]
        if active:
            mastery = sum(state[learner_id][kc_id] for kc_id in active) / len(active)
            probability = guess + (1.0 - slip - guess) * mastery
        else:
            probability = (learner_correct[learner_id] + 1) / (
                learner_attempts[learner_id] + 2
            )
        predictions_by_event[event["event_id"]] = float(
            min(1 - 1e-6, max(1e-6, probability))
        )
        history_by_event[event["event_id"]] = learner_attempts[learner_id]
        for candidate_id in active:
            prior = state[learner_id][candidate_id]
            if event["correct"]:
                posterior = prior * (1 - slip) / (
                    prior * (1 - slip) + (1 - prior) * guess
                )
            else:
                posterior = prior * slip / (
                    prior * slip + (1 - prior) * (1 - guess)
                )
            state[learner_id][candidate_id] = posterior + (1 - posterior) * learn
        learner_attempts[learner_id] += 1
        learner_correct[learner_id] += int(event["correct"])
    return [
        {
            "event_id": event["event_id"],
            "probability": predictions_by_event[event["event_id"]],
            "history_events": history_by_event[event["event_id"]],
        }
        for event in events
    ]


def _metrics(
    events: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    event_ids: set[str],
) -> dict[str, Any]:
    prediction_by_id = {row["event_id"]: row["probability"] for row in predictions}
    selected = [row for row in events if row["event_id"] in event_ids]
    if not selected:
        raise ValueError("selector score has no evaluation events")
    targets = np.asarray([row["correct"] for row in selected], dtype=float)
    probabilities = np.asarray(
        [prediction_by_id[row["event_id"]] for row in selected], dtype=float
    )
    return {
        "n": len(selected),
        "log_loss": float(
            np.mean(
                -(
                    targets * np.log(probabilities)
                    + (1 - targets) * np.log(1 - probabilities)
                )
            )
        ),
        "brier_score": float(np.mean((probabilities - targets) ** 2)),
    }


def _selection_partition(
    events: list[dict[str, Any]], split_design: dict[str, Any]
) -> tuple[list[dict[str, Any]], set[str], set[str], dict[str, Any]]:
    mode = split_design["mode"]
    if mode == "chronological":
        train_label = split_design["train_dataset_split"]
        validation_label = split_design["validation_dataset_split"]
        selected = [
            row
            for row in events
            if row["dataset_split"] in {train_label, validation_label}
        ]
        train_ids = {
            row["event_id"] for row in selected if row["dataset_split"] == train_label
        }
        validation_ids = {
            row["event_id"]
            for row in selected
            if row["dataset_split"] == validation_label
        }
        metadata = {
            "mode": mode,
            "train_dataset_split": train_label,
            "validation_dataset_split": validation_label,
            "train_learners": len({row["learner_id"] for row in selected if row["event_id"] in train_ids}),
            "validation_learners": len({row["learner_id"] for row in selected if row["event_id"] in validation_ids}),
        }
    elif mode == "learner":
        source_labels = set(split_design["source_dataset_splits"])
        selected = [row for row in events if row["dataset_split"] in source_labels]
        learners = sorted({row["learner_id"] for row in selected})
        rng = np.random.default_rng(int(split_design["random_seed"]))
        shuffled = list(learners)
        rng.shuffle(shuffled)
        validation_count = max(
            1, round(len(shuffled) * float(split_design["validation_fraction"]))
        )
        if validation_count >= len(shuffled):
            raise ValueError("learner split needs train and validation learners")
        validation_learners = set(shuffled[:validation_count])
        train_learners = set(shuffled[validation_count:])
        train_ids = {
            row["event_id"] for row in selected if row["learner_id"] in train_learners
        }
        validation_ids = {
            row["event_id"]
            for row in selected
            if row["learner_id"] in validation_learners
        }
        metadata = {
            "mode": mode,
            "source_dataset_splits": sorted(source_labels),
            "random_seed": int(split_design["random_seed"]),
            "validation_fraction": float(split_design["validation_fraction"]),
            "train_learners": len(train_learners),
            "validation_learners": len(validation_learners),
        }
    else:
        raise ValueError(f"unknown selection split mode: {mode}")
    if not train_ids or not validation_ids:
        raise ValueError("selection split produced an empty train or validation set")
    metadata |= {
        "train_events": len(train_ids),
        "validation_events": len(validation_ids),
        "reserved_events_read": False,
    }
    return selected, train_ids, validation_ids, metadata


def score_candidate_policy(
    candidate_inventory: dict[str, Any],
    events: list[dict[str, Any]],
    candidate_ids: list[str],
    model_design: dict[str, Any],
    train_event_ids: set[str],
    evaluation_event_ids: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Score one representation on fixed events with a fixed selector model."""

    if model_design["model"] == "observable_logistic_kt":
        predictions = fit_predict_kc_logistic(
            candidate_inventory,
            events,
            candidate_ids,
            model_design,
            train_event_ids,
        )
    elif model_design["model"] == "bkt":
        predictions = predict_kc_bkt(
            candidate_inventory,
            events,
            candidate_ids,
            model_design,
        )
    else:
        raise ValueError(f"unknown selector model: {model_design['model']}")
    return _metrics(events, predictions, evaluation_event_ids), predictions


def select_kcs(
    candidate_inventory: dict[str, Any],
    development_events: list[dict[str, Any]],
    selection_design: dict[str, Any],
) -> dict[str, Any]:
    """Select on development train/validation evidence and freeze activation rules."""

    development_item_ids = set(candidate_inventory["development_item_ids"])
    nondevelopment_items = {
        row["item_id"] for row in development_events
    } - development_item_ids
    if nondevelopment_items:
        raise ValueError(
            "KC selection received non-development items: "
            f"{sorted(nondevelopment_items)}"
        )
    if any(row.get("grammar_split") not in (None, "development") for row in development_events):
        raise ValueError("KC selection received non-development grammar events")
    candidates = _candidate_lookup(candidate_inventory)
    search = selection_design["search"]
    initial = sorted(
        row["id"]
        for row in candidates.values()
        if row["family"] == search["initial_family"]
        and row["selection_eligible"]
    )
    if not initial:
        raise ValueError("selection has no eligible initial feature candidates")
    additions = sorted(
        row["id"]
        for row in candidates.values()
        if row["family"] in set(search["addition_families"])
        and row["selection_eligible"]
        and row["id"] not in initial
    )
    selection_events, train_ids, validation_ids, split_metadata = _selection_partition(
        development_events, selection_design["selection_split"]
    )
    item_by_event = {row["event_id"]: row["item_id"] for row in selection_events}

    def event_support(candidate_id: str) -> dict[str, int]:
        supporting_items = set(
            candidates[candidate_id]["supporting_development_item_ids"]
        )
        return {
            "train_events": sum(
                item_by_event[event_id] in supporting_items for event_id in train_ids
            ),
            "validation_events": sum(
                item_by_event[event_id] in supporting_items
                for event_id in validation_ids
            ),
        }

    initial_event_support = {
        candidate_id: event_support(candidate_id) for candidate_id in initial
    }
    unsupported_initial = {
        candidate_id: support
        for candidate_id, support in initial_event_support.items()
        if not support["train_events"] or not support["validation_events"]
    }
    addition_event_support = {
        candidate_id: event_support(candidate_id) for candidate_id in additions
    }
    excluded_additions = {
        candidate_id: {
            **support,
            "reason": "zero_train_or_validation_event_support",
        }
        for candidate_id, support in addition_event_support.items()
        if not support["train_events"] or not support["validation_events"]
    }
    additions = [
        candidate_id
        for candidate_id in additions
        if candidate_id not in excluded_additions
    ]
    model_design = selection_design["selector_model"]
    if model_design["model"] not in {"observable_logistic_kt", "bkt"}:
        raise ValueError(f"unknown selector model: {model_design['model']}")
    objective_design = selection_design["objective"]
    metric_name = objective_design["metric"]
    complexity_name = objective_design["complexity"]
    if metric_name != "log_loss":
        raise ValueError(f"unsupported KC-selection objective metric: {metric_name}")
    if complexity_name != "kc_count":
        raise ValueError(
            f"unsupported KC-selection complexity measure: {complexity_name}"
        )
    penalty = float(objective_design["complexity_penalty"])
    minimum_improvement = float(
        objective_design["minimum_improvement"]
    )
    if penalty < 0 or minimum_improvement < 0:
        raise ValueError("selection penalty and minimum improvement must be nonnegative")

    cache: dict[tuple[str, ...], dict[str, Any]] = {}

    def score(candidate_ids: list[str]) -> dict[str, Any]:
        key = tuple(sorted(candidate_ids))
        if key not in cache:
            metrics, _predictions = score_candidate_policy(
                candidate_inventory,
                selection_events,
                list(key),
                model_design,
                train_ids,
                validation_ids,
            )
            cache[key] = {
                **metrics,
                complexity_name: len(key),
                "complexity_penalty": penalty * len(key),
                "objective": metrics[metric_name] + penalty * len(key),
            }
        return cache[key]

    selected = list(initial)
    current = score(selected)
    trace: list[dict[str, Any]] = [
        {
            "step": 0,
            "action": "initial_factorized",
            "candidate_ids": list(selected),
            "score": current,
        }
    ]
    remaining = list(additions)
    while remaining:
        trials = []
        for candidate_id in remaining:
            trial_score = score([*selected, candidate_id])
            trials.append(
                {
                    "candidate_id": candidate_id,
                    "score": trial_score,
                    "objective_improvement": current["objective"]
                    - trial_score["objective"],
                }
            )
        best = sorted(
            trials,
            key=lambda row: (-row["objective_improvement"], row["candidate_id"]),
        )[0]
        if best["objective_improvement"] <= minimum_improvement:
            trace.append(
                {
                    "step": len(trace),
                    "action": "forward_stop",
                    "minimum_improvement": minimum_improvement,
                    "best_rejected": best,
                    "candidate_scores": trials,
                }
            )
            break
        selected.append(best["candidate_id"])
        remaining.remove(best["candidate_id"])
        current = best["score"]
        trace.append(
            {
                "step": len(trace),
                "action": "forward_add",
                "selected": best["candidate_id"],
                "objective_improvement": best["objective_improvement"],
                "score": current,
                "candidate_scores": trials,
            }
        )

    if search["backward_prune"]:
        initial_set = set(initial)
        removable = [
            candidate_id
            for candidate_id in reversed(selected)
            if not (search["preserve_initial"] and candidate_id in initial_set)
        ]
        for candidate_id in removable:
            trial_ids = [row for row in selected if row != candidate_id]
            trial_score = score(trial_ids)
            if trial_score["objective"] <= current["objective"]:
                selected = trial_ids
                current = trial_score
                trace.append(
                    {
                        "step": len(trace),
                        "action": "backward_prune",
                        "pruned": candidate_id,
                        "score": current,
                    }
                )

    selected = sorted(selected)
    selected_rows = [candidates[candidate_id] for candidate_id in selected]
    return {
        "policy_id": f"selected__{selection_design['selection_id']}",
        "description": (
            "Development-only feature base with predictive/parsimony-selected "
            "supported additions; frozen before grammar-holdout projection."
        ),
        "kcs": [
            {
                "id": row["id"],
                "definition": row["definition"],
                "activation": row["activation"],
            }
            for row in selected_rows
        ],
        "selection_metadata": {
            "selection_id": selection_design["selection_id"],
            "candidate_design_id": candidate_inventory["candidate_design_id"],
            "development_cell_ids": candidate_inventory["development_cell_ids"],
            "development_item_ids": candidate_inventory["development_item_ids"],
            "initial_candidate_ids": initial,
            "eligible_addition_ids": additions,
            "initial_event_support": initial_event_support,
            "initial_support_warnings": {
                candidate_id: {
                    **support,
                    "reason": "protected_base_has_zero_train_or_validation_activation",
                }
                for candidate_id, support in unsupported_initial.items()
            },
            "addition_event_support": addition_event_support,
            "excluded_additions": excluded_additions,
            "selected_candidate_ids": selected,
            "selected_support": {
                row["id"]: {
                    "cell_support": row["cell_support"],
                    "item_support": row["item_support"],
                }
                for row in selected_rows
            },
            "split": split_metadata,
            "objective": selection_design["objective"],
            "selector_model": model_design,
            "final_validation_score": current,
            "trace": trace,
            "development_outcomes_read": True,
            "reserved_or_holdout_outcomes_read": False,
            "held_out_grammar_read": False,
        },
    }
