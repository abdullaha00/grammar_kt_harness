#!/usr/bin/env python3
"""Preregister and run the bounded full-v1 collection-design study."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt import baseline_simulation as baseline
from grammar_kt.io import read_jsonl, read_yaml
from scripts.experiments.rq2_kc_misspecification import (
    build_observable_feature_matrix,
    file_sha256,
    fit_observable_logistic,
    load_projection_bundle,
    prediction_metrics,
)


STUDY_ID = "full_v1_collection_design_v1"
DEFAULT_DATASET = ROOT / "data/grammar_kt_full_v1"
DEFAULT_OUTPUT = ROOT / "experiments/full_v1/collection_design_v1"
RQ2_DIR = ROOT / "reports/full_v1_artifacts/rq2_misspecification_v1"
REPRESENTATIONS = (
    "true_kstar",
    "family_union_coarse",
    "structural_split2",
    "exact_cell",
)
LEARNER_COUNTS = (60, 120, 240, 500, 1000)
LEARNER_REPLICATES = 5
OPPORTUNITY_TARGETS = (6, 12, 24)
SIMULATION_SEEDS = (20260830, 20260831, 20260832)
MICRO_LEARNERS = (100, 300, 1000)
MICRO_SEEDS = (20260840, 20260841, 20260842)
MICRO_VOLUME = 60
COMPLEXITY_PENALTY = 0.0005
BOOTSTRAP_REPEATS = 2000
PLAN_SEED = 20260830
FORBIDDEN_SELECTION_FIELDS = frozenset(
    set(baseline.ORACLE_FIELDS) - set(baseline.OBSERVABLE_FIELDS)
) | {
    "active_kc_ids",
    "latent_mastery",
    "mastery",
    "true_probability",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def semantic_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def stable_unit(seed: int, *parts: object) -> float:
    payload = "\x1f".join([str(seed), *(str(part) for part in parts)])
    integer = int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")
    return integer / 2**64


def _write_frozen_json(path: Path, value: Any, label: str) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def _write_frozen_text(path: Path, payload: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def _input_manifest(dataset: Path) -> dict[str, dict[str, Any]]:
    dataset = dataset.resolve()
    paths = {
        "manifest": dataset / "manifest.json",
        "interactions": dataset / "interactions.jsonl.gz",
        "items": dataset / "items/items.jsonl",
        "cells": dataset / "grammar/cells.jsonl",
        "regimes": dataset / "grammar/regime_assignments.jsonl",
        "generator_kcs": dataset / "kcs.jsonl",
        "q_dense": dataset / "q_matrix.csv",
        "q_sparse": dataset / "oracle/q_matrix_sparse.jsonl",
        "simulator_config": ROOT / "modules/simulation/baseline.yaml",
        "rq2_plan": RQ2_DIR / "study_plan.json",
        "rq2_projections": RQ2_DIR / "projections.jsonl",
        "rq2_script": ROOT / "scripts/experiments/rq2_kc_misspecification.py",
        "baseline_simulator": ROOT / "src/grammar_kt/baseline_simulation.py",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"collection-design inputs missing: {missing}")
    return {
        name: {"path": str(path.relative_to(ROOT)), "sha256": file_sha256(path)}
        for name, path in paths.items()
    }


def _load_q_sparse(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path)


def _dataset_true_projection(dataset: Path) -> dict[str, tuple[str, ...]]:
    return {
        str(row["item_id"]): tuple(sorted(str(kc) for kc in row["generator_kc_ids"]))
        for row in read_jsonl(dataset / "oracle/q_matrix_sparse.jsonl")
    }


def fixed_full_representations(
    dataset: Path = DEFAULT_DATASET,
) -> dict[str, dict[str, tuple[str, ...]]]:
    rq2 = load_projection_bundle(RQ2_DIR / "projections.jsonl")
    dataset_truth = _dataset_true_projection(dataset)
    if rq2["true_kstar"] != dataset_truth:
        raise ValueError("RQ2 true_kstar projection differs from the dataset's frozen Q*")
    output = {
        "true_kstar": dataset_truth,
        "family_union_coarse": rq2["coarse_linguistic_families"],
        "structural_split2": rq2["structural_split2"],
        "exact_cell": rq2["exact_cell"],
    }
    if tuple(output) != REPRESENTATIONS:
        raise AssertionError("collection representation order drift")
    return output


def render_projection_bundle(
    projections: dict[str, dict[str, Sequence[str]]]
) -> str:
    return "".join(
        canonical_json(
            {
                "representation_id": representation_id,
                "item_id": item_id,
                "kc_ids": list(projections[representation_id][item_id]),
            }
        )
        + "\n"
        for representation_id in REPRESENTATIONS
        for item_id in sorted(projections[representation_id])
    )


def deterministic_learner_cohort(
    learners: Sequence[str], *, count: int, replicate: int
) -> list[str]:
    """Outcome-free cohort selected by a frozen learner-ID hash."""

    unique = sorted(set(learners))
    if count > len(unique) or count < 2:
        raise ValueError("invalid learner cohort size")
    if count == len(unique):
        if replicate != 0:
            raise ValueError("full cohort has only one unique replicate")
        return unique
    return sorted(
        sorted(
            unique,
            key=lambda learner: (
                stable_unit(PLAN_SEED, "cohort", replicate, learner),
                learner,
            ),
        )[:count]
    )


def deterministic_train_validation(
    learners: Sequence[str], *, count: int, replicate: int
) -> tuple[set[str], set[str]]:
    del count  # Membership is fixed within replicate as nested N increases.
    validation = {
        learner
        for learner in learners
        if stable_unit(PLAN_SEED, "split", replicate, learner) < 0.20
    }
    training = set(learners) - validation
    if not training or not validation:
        raise ValueError("hash split produced an empty learner partition")
    return training, validation


def load_acquisition_only(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load acquisition outcomes and skip probes before accessing ``correct``."""

    events = []
    skipped = 0
    seen_event_ids: set[str] = set()
    probe_started: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            phase = row.get("phase")
            if phase not in {"acquisition", "probe"}:
                raise ValueError(f"unknown public event phase: {phase!r}")
            learner = str(row.get("learner_id", ""))
            if phase == "probe":
                skipped += 1
                probe_started.add(learner)
                continue
            if learner in probe_started:
                raise ValueError("acquisition row follows a terminal probe")
            leaked = sorted(FORBIDDEN_SELECTION_FIELDS & set(row))
            if leaked:
                raise ValueError(
                    f"acquisition selection row contains oracle fields: {leaked}"
                )
            expected = set(baseline.OBSERVABLE_FIELDS)
            if set(row) != expected:
                raise ValueError(
                    "acquisition public fields differ from frozen observable schema: "
                    f"missing={sorted(expected - set(row))}, "
                    f"unknown={sorted(set(row) - expected)}"
                )
            if row.get("grammar_regime") != "seen":
                raise ValueError("full-v1 acquisition unexpectedly uses non-seen grammar")
            sequence = int(row["sequence_index"])
            if isinstance(row["correct"], bool) or row["correct"] not in {0, 1}:
                raise ValueError("acquisition correct must be integer 0/1")
            event_id = f"{learner}::{sequence:04d}"
            if event_id in seen_event_ids:
                raise ValueError("duplicate public acquisition event ID")
            seen_event_ids.add(event_id)
            events.append(
                {
                    "event_id": event_id,
                    "learner_id": learner,
                    "item_id": str(row["item_id"]),
                    "sequence_index": sequence,
                    "correct": int(row["correct"]),
                    "phase": "acquisition",
                    "updates_history": True,
                    "dataset_split": "selection_acquisition",
                    "grammar_regime": "seen",
                }
            )
    return events, {
        "acquisition_outcomes_read": len(events),
        "probe_rows_skipped_before_correct_access": skipped,
        "probe_outcomes_read": False,
    }


def _validation_fit(
    events: Sequence[dict[str, Any]],
    projection: dict[str, Sequence[str]],
    train_learners: set[str],
    validation_learners: set[str],
) -> tuple[dict[str, Any], dict[str, float]]:
    x, kc_ids = build_observable_feature_matrix(events, projection)
    y = np.asarray([int(row["correct"]) for row in events], dtype=np.int8)
    train = np.asarray([str(row["learner_id"]) in train_learners for row in events])
    validation = np.asarray(
        [str(row["learner_id"]) in validation_learners for row in events]
    )
    if not np.any(train) or not np.any(validation):
        raise ValueError("learner-disjoint split is empty")
    scaler = StandardScaler()
    x_train = scaler.fit_transform(x[train])
    model = LogisticRegression(C=1.0, max_iter=500, random_state=PLAN_SEED)
    model.fit(x_train, y[train])
    probability = np.clip(
        model.predict_proba(scaler.transform(x[validation]))[:, 1], 1e-6, 1 - 1e-6
    )
    validation_events = [
        row for row, keep in zip(events, validation, strict=True) if keep
    ]
    metrics = prediction_metrics(y[validation], probability)
    return {
        **metrics,
        "hypothesis_kcs": len(kc_ids),
        "training_learners": len(train_learners),
        "validation_learners": len(validation_learners),
        "training_events": int(train.sum()),
        "validation_events": int(validation.sum()),
        "converged": bool(np.max(model.n_iter_) < model.max_iter),
    }, {
        row["event_id"]: float(value)
        for row, value in zip(validation_events, probability, strict=True)
    }


def _winner_ids(scores: dict[str, float], *, tolerance: float = 1e-12) -> list[str]:
    best = min(scores.values())
    return sorted(key for key, value in scores.items() if value <= best + tolerance)


def _paired_learner_interval(
    events: Sequence[dict[str, Any]],
    reference: dict[str, float],
    candidate: dict[str, float],
    *,
    seed: int,
) -> dict[str, Any]:
    by_learner: dict[str, list[float]] = defaultdict(list)
    for row in events:
        event_id = row["event_id"]
        y = float(row["correct"])
        left = min(1 - 1e-6, max(1e-6, reference[event_id]))
        right = min(1 - 1e-6, max(1e-6, candidate[event_id]))
        left_loss = -(y * math.log(left) + (1 - y) * math.log(1 - left))
        right_loss = -(y * math.log(right) + (1 - y) * math.log(1 - right))
        by_learner[str(row["learner_id"])].append(right_loss - left_loss)
    values = np.asarray([mean(rows) for _learner, rows in sorted(by_learner.items())])
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(values), size=(BOOTSTRAP_REPEATS, len(values)))
    draws = values[sampled].mean(axis=1)
    return {
        "candidate_minus_kstar_log_loss": float(values.mean()),
        "interval_95": [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))],
        "learners": len(values),
        "repeats": BOOTSTRAP_REPEATS,
        "seed": seed,
    }


def run_learner_stability(
    dataset: Path, projections: dict[str, dict[str, tuple[str, ...]]]
) -> dict[str, Any]:
    events, boundary = load_acquisition_only(dataset / "interactions.jsonl.gz")
    all_learners = sorted({row["learner_id"] for row in events})
    by_learner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in events:
        by_learner[row["learner_id"]].append(row)
    rows = []
    final_predictions = {}
    final_validation_events: list[dict[str, Any]] = []
    for count in LEARNER_COUNTS:
        replicates = 1 if count == len(all_learners) else LEARNER_REPLICATES
        for replicate in range(replicates):
            cohort = deterministic_learner_cohort(
                all_learners, count=count, replicate=replicate
            )
            train_learners, validation_learners = deterministic_train_validation(
                cohort, count=count, replicate=replicate
            )
            selected_events = [row for learner in cohort for row in by_learner[learner]]
            scores = {}
            predictions = {}
            for representation_id in REPRESENTATIONS:
                score, prediction = _validation_fit(
                    selected_events,
                    projections[representation_id],
                    train_learners,
                    validation_learners,
                )
                score["penalized_objective"] = score["log_loss"] + (
                    COMPLEXITY_PENALTY * score["hypothesis_kcs"]
                )
                scores[representation_id] = score
                predictions[representation_id] = prediction
            predictive_winners = _winner_ids(
                {key: value["log_loss"] for key, value in scores.items()}
            )
            objective_winners = _winner_ids(
                {key: value["penalized_objective"] for key, value in scores.items()}
            )
            rows.append(
                {
                    "learner_count": count,
                    "replicate": replicate,
                    "cohort_sha256": semantic_sha256(cohort),
                    "train_learners": len(train_learners),
                    "validation_learners": len(validation_learners),
                    "scores": scores,
                    "predictive_winner_ids": predictive_winners,
                    "penalized_objective_winner_ids": objective_winners,
                    "kstar_predictive_selected": "true_kstar" in predictive_winners,
                    "kstar_objective_selected": "true_kstar" in objective_winners,
                }
            )
            if count == 1000:
                final_predictions = predictions
                final_validation_events = [
                    row for row in selected_events if row["learner_id"] in validation_learners
                ]
    frequencies = {}
    for count in LEARNER_COUNTS:
        selected = [row for row in rows if row["learner_count"] == count]
        frequencies[str(count)] = {
            "replicates": len(selected),
            "kstar_predictive_selection_frequency": mean(
                int(row["kstar_predictive_selected"]) for row in selected
            ),
            "kstar_penalized_selection_frequency": mean(
                int(row["kstar_objective_selected"]) for row in selected
            ),
            "predictive_winner_counts": dict(
                sorted(
                    Counter(
                        winner
                        for row in selected
                        for winner in row["predictive_winner_ids"]
                    ).items()
                )
            ),
            "penalized_winner_counts": dict(
                sorted(
                    Counter(
                        winner
                        for row in selected
                        for winner in row["penalized_objective_winner_ids"]
                    ).items()
                )
            ),
        }
    intervals = {
        candidate_id: _paired_learner_interval(
            final_validation_events,
            final_predictions["true_kstar"],
            final_predictions[candidate_id],
            seed=PLAN_SEED,
        )
        for candidate_id in REPRESENTATIONS[1:]
    }
    return {
        "conditions": rows,
        "selection_frequency": frequencies,
        "n1000_paired_validation_intervals": intervals,
        "boundary_audit": boundary
        | {
            "selection_uses_acquisition_only": True,
            "learner_disjoint_fit_validation": True,
            "probe_outcomes_influence_winners": False,
        },
    }


def _observable_events_from_baseline(
    items: Sequence[dict[str, Any]],
    kcs: Sequence[dict[str, Any]],
    q_rows: Sequence[dict[str, Any]],
    regimes: dict[str, str],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    events = []
    digest = hashlib.sha256()
    for interaction, _discarded_oracle in baseline.iter_baseline_rows(
        items, kcs, q_rows, regimes, config, seed=int(config["seed"])
    ):
        row = {
            **interaction,
            "event_id": f"{interaction['learner_id']}::{int(interaction['sequence_index']):04d}",
            "updates_history": interaction["phase"] == "acquisition",
            "dataset_split": "train" if interaction["phase"] == "acquisition" else "test",
        }
        events.append(row)
        digest.update((canonical_json(interaction) + "\n").encode())
    return events, digest.hexdigest()


def _metrics_by_regime(
    events: Sequence[dict[str, Any]], probability: np.ndarray
) -> dict[str, Any]:
    probes = [row for row in events if row["phase"] == "probe"]
    targets = np.asarray([int(row["correct"]) for row in probes], dtype=np.int8)
    regimes = np.asarray([str(row["grammar_regime"]) for row in probes])
    output = {"all_probe": prediction_metrics(targets, probability)}
    for regime in ("seen", "unseen_combination", "unseen_value"):
        mask = regimes == regime
        output[regime] = prediction_metrics(targets[mask], probability[mask])
    return output


def run_opportunity_study(
    dataset: Path, projections: dict[str, dict[str, tuple[str, ...]]]
) -> dict[str, Any]:
    items = read_jsonl(dataset / "items/items.jsonl")
    kcs = read_jsonl(dataset / "kcs.jsonl")
    q_rows = read_jsonl(dataset / "oracle/q_matrix_sparse.jsonl")
    regimes = {
        row["cell_id"]: row["grammar_regime"]
        for row in read_jsonl(dataset / "grammar/regime_assignments.jsonl")
    }
    base_config = read_yaml(ROOT / "modules/simulation/baseline.yaml")
    q_by_item = {
        str(row["item_id"]): tuple(str(kc) for kc in row["generator_kc_ids"])
        for row in q_rows
    }
    rows = []
    for target in OPPORTUNITY_TARGETS:
        for seed in SIMULATION_SEEDS:
            config = copy.deepcopy(base_config)
            config["learners"] = 500
            config["seed"] = seed
            config["schedule"]["acquisition"][
                "target_opportunities_per_seen_kc"
            ] = target
            events, event_digest = _observable_events_from_baseline(
                items, kcs, q_rows, regimes, config
            )
            scores = {}
            for representation_id in REPRESENTATIONS:
                probability, fit = fit_observable_logistic(
                    events, projections[representation_id], random_seed=PLAN_SEED
                )
                scores[representation_id] = {
                    "fit": fit,
                    "metrics": _metrics_by_regime(events, probability),
                }
            acquisition_rows = sum(row["phase"] == "acquisition" for row in events)
            first_learner = min(str(row["learner_id"]) for row in events)
            opportunity_counts: Counter[str] = Counter(
                kc_id
                for row in events
                if row["phase"] == "acquisition"
                and str(row["learner_id"]) == first_learner
                for kc_id in q_by_item[str(row["item_id"])]
            )
            if min(opportunity_counts.values()) < target:
                raise AssertionError("Q-balanced schedule missed its minimum KC target")
            rows.append(
                {
                    "target_opportunities_per_seen_kc": target,
                    "seed": seed,
                    "learners": 500,
                    "events": len(events),
                    "acquisition_rows_per_learner": acquisition_rows // 500,
                    "realized_seen_kc_opportunities": {
                        "minimum": min(opportunity_counts.values()),
                        "median": float(median(opportunity_counts.values())),
                        "maximum": max(opportunity_counts.values()),
                        "by_kc": dict(sorted(opportunity_counts.items())),
                    },
                    "event_stream_semantic_sha256": event_digest,
                    "same_events_reused_across_representations": True,
                    "scores": scores,
                }
            )
    summary = {}
    for target in OPPORTUNITY_TARGETS:
        target_rows = [
            row for row in rows if row["target_opportunities_per_seen_kc"] == target
        ]
        summary[str(target)] = {}
        for representation_id in REPRESENTATIONS:
            summary[str(target)][representation_id] = {}
            for regime in ("all_probe", "seen", "unseen_combination", "unseen_value"):
                values = [
                    row["scores"][representation_id]["metrics"][regime]["log_loss"]
                    for row in target_rows
                ]
                summary[str(target)][representation_id][regime] = {
                    "mean_log_loss": float(mean(values)),
                    "seed_range": [float(min(values)), float(max(values))],
                }
    return {
        "conditions": rows,
        "summary": summary,
        "boundary_audit": {
            "baseline_dataset_mutated": False,
            "learner_oracle_rows_exposed_to_predictor": False,
            "probe_rows_non_updating": True,
            "same_events_across_representation_comparisons": True,
        },
    }


def _q_geometry(
    projection: dict[str, Sequence[str]], *, kc_universe: Sequence[str] | None = None
) -> dict[str, Any]:
    item_ids = sorted(projection)
    active_kcs = {kc for active in projection.values() for kc in active}
    kc_ids = sorted(active_kcs if kc_universe is None else set(kc_universe))
    if active_kcs - set(kc_ids):
        raise ValueError("projection uses a KC outside the declared universe")
    matrix = np.asarray(
        [[int(kc in projection[item]) for kc in kc_ids] for item in item_ids],
        dtype=np.int8,
    )
    row_counts = Counter(tuple(row.tolist()) for row in matrix)
    columns: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for index, kc_id in enumerate(kc_ids):
        columns[tuple(matrix[:, index].tolist())].append(kc_id)
    support = matrix.sum(axis=0).tolist() if kc_ids else []
    return {
        "items": len(item_ids),
        "kcs": len(kc_ids),
        "edges": int(matrix.sum()),
        "rank": int(np.linalg.matrix_rank(matrix)) if kc_ids else 0,
        "unique_q_rows": len(row_counts),
        "duplicate_q_rows": len(item_ids) - len(row_counts),
        "q_row_multiplicity": dict(sorted(Counter(row_counts.values()).items())),
        "identical_q_column_groups": [
            sorted(ids) for ids in columns.values() if len(ids) > 1
        ],
        "item_support_per_kc": {
            "minimum": int(min(support)) if support else 0,
            "median": float(median(support)) if support else 0.0,
            "maximum": int(max(support)) if support else 0,
            "by_kc": dict(zip(kc_ids, map(int, support), strict=True)),
        },
    }


def run_items_per_kc_audit(
    dataset: Path, true_projection: dict[str, tuple[str, ...]]
) -> dict[str, Any]:
    items = read_jsonl(dataset / "items/items.jsonl")
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in items:
        by_cell[row["cell_id"]].append(row)
    if any(len(rows) > 2 for rows in by_cell.values()):
        raise ValueError("max-two audit requires at most two fixed items per cell")
    for cell_id, rows in by_cell.items():
        activations = {
            tuple(sorted(true_projection[row["item_id"]])) for row in rows
        }
        if len(activations) != 1:
            raise ValueError(f"within-cell Q rows differ for {cell_id}")
    max_one_items = [
        sorted(
            rows,
            key=lambda row: (
                int(row.get("selection_metadata", {}).get("rank", 999)),
                row["item_id"],
            ),
        )[0]
        for _cell, rows in sorted(by_cell.items())
    ]
    max_one_ids = {row["item_id"] for row in max_one_items}
    max_one_projection = {
        item_id: true_projection[item_id] for item_id in sorted(max_one_ids)
    }
    max_two_projection = dict(true_projection)
    kc_universe = sorted({kc for active in true_projection.values() for kc in active})
    one = _q_geometry(max_one_projection, kc_universe=kc_universe)
    two = _q_geometry(max_two_projection, kc_universe=kc_universe)
    one_patterns = {
        tuple(sorted(active)) for active in max_one_projection.values()
    }
    two_patterns = {
        tuple(sorted(active)) for active in max_two_projection.values()
    }
    adds_diversity = bool(two_patterns - one_patterns)
    return {
        "max_one_per_cell": one,
        "max_two_per_cell": two,
        "comparison": {
            "additional_items": two["items"] - one["items"],
            "additional_unique_q_rows": len(two_patterns - one_patterns),
            "column_rank_change": two["rank"] - one["rank"],
            "activation_equivalence_change": len(two["identical_q_column_groups"])
            - len(one["identical_q_column_groups"]),
            "second_variants_add_structural_activation_diversity": adds_diversity,
            "structural_result": (
                "Second within-cell variants add a new activation pattern."
                if adds_diversity
                else "Within-cell variants duplicate the cell's Q row: they increase "
                "item support but add no Q activation pattern or rank."
            ),
            "scope_caveat": (
                "The simulator has no item-memory or lexical-difficulty state; "
                "this cannot establish the value of lexical diversity for humans."
            ),
        },
    }


def micro_designs() -> dict[str, dict[str, int]]:
    return {
        "all_ab_no_anchors": {"a_only": 0, "b_only": 0, "a_plus_b": 60},
        "sparse_anchors": {"a_only": 6, "b_only": 6, "a_plus_b": 48},
        "balanced_anchors": {"a_only": 20, "b_only": 20, "a_plus_b": 20},
    }


def micro_world_projection(world: str) -> dict[str, tuple[str, ...]]:
    if world == "factorized_ab":
        return {
            "a_only": ("A",),
            "b_only": ("B",),
            "a_plus_b": ("A", "B"),
        }
    if world == "planted_abi":
        return {
            "a_only": ("A",),
            "b_only": ("B",),
            "a_plus_b": ("A", "B", "I"),
        }
    raise ValueError(f"unknown micro world: {world}")


def micro_hypotheses(world: str) -> dict[str, dict[str, tuple[str, ...]]]:
    union = {
        "a_only": ("U",),
        "b_only": ("U",),
        "a_plus_b": ("U",),
    }
    missing = {
        "a_only": ("A",),
        "b_only": ("B",),
        "a_plus_b": ("A", "B"),
    }
    interaction = {
        "a_only": ("A",),
        "b_only": ("B",),
        "a_plus_b": ("A", "B", "I"),
    }
    if world == "factorized_ab":
        return {
            "true_factorized": missing,
            "union_merge": union,
            "spurious_intersection": interaction,
        }
    if world == "planted_abi":
        return {
            "true_planted_intersection": interaction,
            "union_merge": union,
            "missing_intersection": missing,
        }
    raise ValueError(world)


def micro_q_audit(world: str, counts: dict[str, int]) -> dict[str, Any]:
    truth = micro_world_projection(world)
    rows = {
        f"{item_type}_{index:02d}": truth[item_type]
        for item_type, count in counts.items()
        for index in range(1, count + 1)
    }
    geometry = _q_geometry(rows)
    geometry["semantics"] = {
        "matrix_scope": "60 acquisition opportunities represented as repeated activation rows",
        "union_merge": "U activates on A-only OR B-only OR A+B",
        "intersection": "I activates only on A+B",
        "union_is_not_intersection": True,
        "response_volume_cannot_change_rank_or_identical_columns": True,
    }
    return geometry


def simulate_micro_events(
    *, world: str, design: dict[str, int], learners: int, seed: int
) -> tuple[list[dict[str, Any]], str]:
    truth = micro_world_projection(world)
    kc_ids = sorted({kc for active in truth.values() for kc in active})
    occurrence_rows = [
        (item_type, exposure)
        for item_type, count in design.items()
        for exposure in range(1, count + 1)
    ]
    events = []
    digest = hashlib.sha256()
    for learner_number in range(1, learners + 1):
        learner_id = f"micro_{learner_number:04d}"
        mastery = {
            kc_id: float(
                baseline._keyed_rng(seed, "micro", "initial", learner_number, kc_id).beta(2, 2)
            )
            for kc_id in kc_ids
        }
        ordered = sorted(
            occurrence_rows,
            key=lambda row: (
                stable_unit(seed, "micro", learner_number, "order", row[0], row[1]),
                row,
            ),
        )
        sequence = 0
        for item_type, exposure in ordered:
            sequence += 1
            active = truth[item_type]
            probability = 0.1 + 0.8 * min(mastery[kc] for kc in active)
            draw = stable_unit(seed, "micro", learner_number, "response", item_type, exposure)
            correct = int(draw < probability)
            for kc_id in active:
                mastery[kc_id] += 0.02 * (1 - mastery[kc_id])
            row = {
                "event_id": f"{learner_id}::{sequence:03d}",
                "learner_id": learner_id,
                "item_id": item_type,
                "sequence_index": sequence,
                "correct": correct,
                "phase": "acquisition",
                "updates_history": True,
                "dataset_split": "train",
                "grammar_regime": "seen",
            }
            events.append(row)
            digest.update((canonical_json(row) + "\n").encode())
        for item_type in ("a_only", "b_only", "a_plus_b"):
            sequence += 1
            active = truth[item_type]
            probability = 0.1 + 0.8 * min(mastery[kc] for kc in active)
            draw = stable_unit(seed, "micro", learner_number, "probe", item_type)
            row = {
                "event_id": f"{learner_id}::{sequence:03d}",
                "learner_id": learner_id,
                "item_id": item_type,
                "sequence_index": sequence,
                "correct": int(draw < probability),
                "phase": "probe",
                "updates_history": False,
                "dataset_split": "test",
                "grammar_regime": "seen",
            }
            events.append(row)
            digest.update((canonical_json(row) + "\n").encode())
    return events, digest.hexdigest()


def run_anchor_microstudy() -> dict[str, Any]:
    designs = micro_designs()
    q_audit = {
        world: {
            design_id: micro_q_audit(world, counts)
            for design_id, counts in designs.items()
        }
        for world in ("factorized_ab", "planted_abi")
    }
    rows = []
    for world in ("factorized_ab", "planted_abi"):
        hypotheses = micro_hypotheses(world)
        true_id = next(iter(hypotheses))
        for design_id, counts in designs.items():
            for learners in MICRO_LEARNERS:
                for seed in MICRO_SEEDS:
                    events, event_digest = simulate_micro_events(
                        world=world, design=counts, learners=learners, seed=seed
                    )
                    scores = {}
                    for representation_id, projection in hypotheses.items():
                        probability, fit = fit_observable_logistic(
                            events, projection, random_seed=PLAN_SEED
                        )
                        probes = [row for row in events if row["phase"] == "probe"]
                        score = prediction_metrics(
                            [int(row["correct"]) for row in probes], probability
                        )
                        scores[representation_id] = {"fit": fit, "probe": score}
                    true_loss = scores[true_id]["probe"]["log_loss"]
                    rows.append(
                        {
                            "world": world,
                            "design": design_id,
                            "learners": learners,
                            "seed": seed,
                            "opportunities_per_learner": sum(counts.values()),
                            "terminal_probe_rows_per_learner": 3,
                            "total_rows_per_learner": sum(counts.values()) + 3,
                            "event_stream_semantic_sha256": event_digest,
                            "same_events_reused_across_representations": True,
                            "q_rank": q_audit[world][design_id]["rank"],
                            "identical_q_column_groups": q_audit[world][design_id][
                                "identical_q_column_groups"
                            ],
                            "scores": scores,
                            "delta_log_loss_vs_true": {
                                representation_id: score["probe"]["log_loss"] - true_loss
                                for representation_id, score in scores.items()
                            },
                        }
                    )
    summary = {}
    for world in ("factorized_ab", "planted_abi"):
        summary[world] = {}
        for design_id in designs:
            summary[world][design_id] = {}
            for learners in MICRO_LEARNERS:
                selected = [
                    row
                    for row in rows
                    if row["world"] == world
                    and row["design"] == design_id
                    and row["learners"] == learners
                ]
                candidates = [
                    key for key in selected[0]["scores"] if not key.startswith("true_")
                ]
                summary[world][design_id][str(learners)] = {
                    candidate: {
                        "mean_delta_log_loss_vs_true": float(
                            mean(row["delta_log_loss_vs_true"][candidate] for row in selected)
                        ),
                        "seed_range": [
                            float(min(row["delta_log_loss_vs_true"][candidate] for row in selected)),
                            float(max(row["delta_log_loss_vs_true"][candidate] for row in selected)),
                        ],
                    }
                    for candidate in candidates
                }
    return {
        "q_structure": q_audit,
        "seedwise_conditions": rows,
        "summary": summary,
        "semantics": {
            "union_merge": "one U column is active on A-only, B-only, and A+B (OR/union)",
            "intersection": "I is active only on A+B (AND/intersection)",
            "union_is_not_intersection": True,
            "all_ab_identifiability": (
                "A, B (and planted I) columns are identical without anchors; "
                "increasing N cannot change this structural equivalence."
            ),
        },
        "boundary_audit": {
            "same_events_across_pure_representation_comparisons": True,
            "probe_updates_history": False,
            "fixed_opportunities_per_learner": MICRO_VOLUME,
            "terminal_probe_rows_per_learner": 3,
            "probe_scope": "A-only, B-only, and A+B for every acquisition design",
            "oracle_state_exposed_to_predictors": False,
        },
    }


def create_plan(dataset: Path, output: Path) -> dict[str, Any]:
    dataset = dataset.resolve()
    output = output.resolve()
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "FROZEN_BASELINE_COMPLETE":
        raise ValueError("collection study requires frozen full v1")
    if (output / "results.json").exists():
        raise FileExistsError("refusing to preregister after collection results exist")
    projections = fixed_full_representations(dataset)
    projection_payload = render_projection_bundle(projections)
    _write_frozen_text(output / "full_v1_projections.jsonl", projection_payload, "projection bundle")
    micro = {
        "designs": micro_designs(),
        "worlds": {
            "factorized_ab": {
                "generator_q": micro_world_projection("factorized_ab"),
                "representations": micro_hypotheses("factorized_ab"),
            },
            "planted_abi": {
                "generator_q": micro_world_projection("planted_abi"),
                "representations": micro_hypotheses("planted_abi"),
            },
        },
        "learners": list(MICRO_LEARNERS),
        "seeds": list(MICRO_SEEDS),
        "fixed_opportunities_per_learner": MICRO_VOLUME,
        "terminal_probe_rows_per_learner": 3,
        "probe_scope": "common A-only, B-only, A+B terminal probes; non-updating",
        "generator_assumptions": {
            "initial_mastery": "independent Beta(2,2) per learner/KC",
            "response": "0.10 + 0.80 * minimum(active mastery)",
            "learning": "all active KCs += 0.02 * (1-mastery), outcome-independent",
            "forgetting": "none",
            "order": "keyed SHA-256 rank of 60 acquisition opportunities",
            "cross_world_pairing": "same A/B initial streams, item order, and response draws",
        },
        "interpretation_rule": {
            "structural": "rank/equivalence is primary; N cannot repair identical Q columns",
            "factorized_negative_control": "spurious I should show no stable probe advantage over true factorized A/B",
            "planted_positive_control": "with full-rank anchor designs, missing I should underperform planted A/B/I",
            "all_ab": "predictive ties/differences cannot establish separate KC recovery because columns are identical",
        },
    }
    _write_frozen_json(output / "microstudy_design.json", micro, "microstudy design")
    plan = {
        "study_id": STUDY_ID,
        "status": "FROZEN_ANALYSIS_PLAN_BEFORE_THIS_STUDY_EXECUTION",
        "parts": {
            "A_learner_count": {
                "counts": list(LEARNER_COUNTS),
                "replicates": LEARNER_REPLICATES,
                "full_n_replicates": 1,
                "cohort_rule": "SHA-256 learner-ID rank",
                "nested_cohorts": True,
                "split": "learner-disjoint stable SHA-256 80/20 membership",
                "outcomes": "acquisition only; probes skipped before correct access",
                "evidence_status": "preregistered secondary analysis of already-available full-v1 outcomes",
                "report_winners": ["raw validation log loss", "log loss + 0.0005 * KC count"],
            },
            "B_opportunities": {
                "targets": list(OPPORTUNITY_TARGETS),
                "learners": 500,
                "seeds": list(SIMULATION_SEEDS),
                "simulator": "frozen K*/Q*, beta(2,2), min, guess/slip=.1, learning=.02, no forgetting",
                "probe": "one all-bank terminal non-updating probe",
                "target_semantics": "minimum opportunities per seen generator KC, not rows per learner",
            },
            "C_items_per_kc": {
                "conditions": ["max_one_per_cell", "max_two_per_cell"],
                "metrics": ["support", "rank", "Q row diversity", "Q column equivalence"],
                "human_lexical_claim_allowed": False,
            },
            "D_anchor_microstudy": micro,
        },
        "representations": {
            "true_kstar": "18-KC generator reference",
            "family_union_coarse": "six OR/union family merges; not interactions",
            "structural_split2": "outcome-free two-way context splits",
            "exact_cell": "one KC per exact GrammarCell",
        },
        "common_predictor": {
            "model": "observable PFA-like logistic",
            "features": [
                "learner correctness history",
                "active-KC correctness history",
                "active-KC opportunity history",
                "KC count",
                "KC indicators",
            ],
            "standardize": True,
            "C": 1.0,
            "max_iterations": 500,
            "seed": PLAN_SEED,
            "complexity_penalty": COMPLEXITY_PENALTY,
        },
        "scientific_boundary": {
            "plans_and_projections_frozen_before_outcomes": True,
            "probe_outcomes_used_to_choose_representations": False,
            "same_events_reused_for_pure_representation_comparisons": True,
            "private_oracle_used_by_selection_or_prediction": False,
            "all_probes_non_updating": True,
            "baseline_dataset_mutated": False,
        },
        "inputs": _input_manifest(dataset),
        "frozen_artifacts": {
            "full_v1_projections": {
                "path": "full_v1_projections.jsonl",
                "sha256": hashlib.sha256(projection_payload.encode()).hexdigest(),
            },
            "microstudy_design": {
                "path": "microstudy_design.json",
                "sha256": file_sha256(output / "microstudy_design.json"),
            },
        },
        "implementation": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)),
            "sha256": file_sha256(Path(__file__).resolve()),
        },
        "exact_commands": {
            "plan": ".venv/bin/python scripts/experiments/collection_design.py --stage plan",
            "run": ".venv/bin/python scripts/experiments/collection_design.py --stage run",
        },
    }
    plan["plan_semantic_sha256"] = semantic_sha256(plan)
    _write_frozen_json(output / "study_plan.json", plan, "collection plan")
    return plan


def _validate_plan(
    dataset: Path, output: Path
) -> tuple[dict[str, Any], dict[str, dict[str, tuple[str, ...]]]]:
    dataset = dataset.resolve()
    output = output.resolve()
    plan = json.loads((output / "study_plan.json").read_text(encoding="utf-8"))
    unsigned = {key: value for key, value in plan.items() if key != "plan_semantic_sha256"}
    if plan.get("plan_semantic_sha256") != semantic_sha256(unsigned):
        raise ValueError("collection plan semantic hash mismatch")
    if plan.get("study_id") != STUDY_ID:
        raise ValueError("collection plan study ID mismatch")
    if plan.get("status") != "FROZEN_ANALYSIS_PLAN_BEFORE_THIS_STUDY_EXECUTION":
        raise ValueError("collection run requires preregistered plan")
    if file_sha256(Path(__file__).resolve()) != plan["implementation"]["sha256"]:
        raise ValueError("collection implementation changed after planning")
    if _input_manifest(dataset) != plan["inputs"]:
        raise ValueError("collection input changed after planning")
    for row in plan["frozen_artifacts"].values():
        if file_sha256(output / row["path"]) != row["sha256"]:
            raise ValueError(f"collection frozen artifact changed: {row['path']}")
    bundle = load_projection_bundle(output / "full_v1_projections.jsonl")
    if set(bundle) != set(REPRESENTATIONS):
        raise ValueError("collection projection bundle differs")
    return plan, bundle


def run_study(dataset: Path, output: Path) -> dict[str, Any]:
    dataset = dataset.resolve()
    output = output.resolve()
    plan, projections = _validate_plan(dataset, output)
    before = _input_manifest(dataset)
    learner_stability = run_learner_stability(dataset, projections)
    opportunity_study = run_opportunity_study(dataset, projections)
    item_audit = run_items_per_kc_audit(dataset, projections["true_kstar"])
    anchor = run_anchor_microstudy()
    after = _input_manifest(dataset)
    if before != after:
        raise AssertionError("frozen baseline changed during collection study")
    result = {
        "study_id": STUDY_ID,
        "status": "FULL_COLLECTION_DESIGN_COMPLETE",
        "plan_sha256": file_sha256(output / "study_plan.json"),
        "plan_semantic_sha256": plan["plan_semantic_sha256"],
        "A_learner_count_stability": learner_stability,
        "B_opportunities_per_learner": opportunity_study,
        "C_items_per_kc": item_audit,
        "D_anchor_identifiability": anchor,
        "boundary_audit": {
            "baseline_inputs_before": before,
            "baseline_inputs_after": after,
            "baseline_immutable": before == after,
            "probe_outcomes_used_for_selection": False,
            "same_events_across_pure_representation_comparisons": True,
            "oracle_state_exposed_to_predictor": False,
            "all_probes_non_updating": True,
        },
    }
    result["result_semantic_sha256"] = semantic_sha256(result)
    _write_frozen_json(output / "results.json", result, "collection results")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("plan", "run"), required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.stage == "plan":
        result = create_plan(args.dataset, args.output)
        artifact = args.output / "study_plan.json"
    else:
        result = run_study(args.dataset, args.output)
        artifact = args.output / "results.json"
    print(
        json.dumps(
            {
                "status": result["status"],
                "artifact": str(artifact.resolve().relative_to(ROOT)),
                "sha256": file_sha256(artifact),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
