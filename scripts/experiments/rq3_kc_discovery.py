#!/usr/bin/env python3
"""Observable-only KC discovery and name-free recovery evaluation for full v1.

The command boundary is deliberately strict:

``plan``
    Freeze all candidate, selection, cohort, and evaluation decisions.
``select``
    Read public grammar/items and *seen acquisition* outcomes only.  It cannot
    accept or load generator KCs, Q*, oracle rows, or probe outcomes.
``evaluate``
    Require an already-written frozen selection artifact, then load Q* solely
    for structural evaluation and use probes solely for final prediction.

This is an experiment runner, not part of baseline dataset construction.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import read_jsonl, read_yaml, write_json
from grammar_kt.kc import activation_matches
from grammar_kt.kc_candidates import make_kc_candidates


STUDY_ID = "full_v1_rq3_observable_kc_discovery_v1"
PLAN_VERSION = 1
DEFAULT_DATASET = ROOT / "data/grammar_kt_full_v1"
DEFAULT_ARTIFACT_DIR = ROOT / "experiments/full_v1/rq3_kc_discovery_v1"
PUBLIC_EVENT_FIELDS = {
    "learner_id",
    "item_id",
    "sequence_index",
    "correct",
    "phase",
    "pass_index",
    "grammar_regime",
}
FORBIDDEN_SELECTION_TOKENS = {
    "generator_kc_ids",
    "mastery_before",
    "mastery_after",
    "response_probability",
    "item_difficulty",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _resolve(recorded: str) -> Path:
    path = Path(recorded)
    return path if path.is_absolute() else ROOT / path


def _stable_unit(*parts: object) -> float:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return integer / float(2**64)


def make_plan(dataset: Path = DEFAULT_DATASET) -> dict[str, Any]:
    """Return the complete preregistered design without reading any outcomes."""

    selection_inputs = {
        "interactions": dataset / "interactions.jsonl.gz",
        "cells": dataset / "grammar/cells.jsonl",
        "regimes": dataset / "grammar/regime_assignments.jsonl",
        "items": dataset / "items/items.jsonl",
        "grammar_schema": ROOT / "modules/grammar/canonical/schema.yaml",
        "candidate_design": ROOT / "modules/kcs/candidate_design.yaml",
        "operation_declarations": (
            ROOT / "modules/grammar/canonical/english_operations.yaml"
        ),
        "retained_selection_design": ROOT / "modules/kcs/selection.yaml",
    }
    evaluation_only_inputs = {
        "generator_kcs": dataset / "kcs.jsonl",
        "true_q_sparse": dataset / "oracle/q_matrix_sparse.jsonl",
    }
    all_paths = selection_inputs | evaluation_only_inputs
    missing = [str(path) for path in all_paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"RQ3 plan inputs are missing: {missing}")
    plan = {
        "study_id": STUDY_ID,
        "plan_version": PLAN_VERSION,
        "status": "FROZEN_BEFORE_PILOT_AND_FINAL_EXECUTION",
        "scientific_boundary": {
            "selection_reads": [
                "canonical GrammarCell features",
                "fixed item-to-cell relations",
                "seen acquisition outcomes",
            ],
            "selection_never_reads": [
                "generator KCs K*",
                "true Q-matrix Q*",
                "private oracle learner truth",
                "probe outcomes",
                "unseen-combination or unseen-value outcomes",
            ],
            "evaluation_truth_loaded_only_after_frozen_selection": True,
            "candidate_space_ceiling_is_not_learner_evidence_recovery": True,
        },
        "cohorts": {
            "pilot": {
                "learners": 120,
                "status": "development_diagnostic_only",
            },
            "final": {"learners": 1000, "status": "paper_facing_final"},
        },
        "candidate_space": {
            "seen_grammar_only_during_construction": True,
            "families": [
                "atomic_feature_values",
                "declared_reusable_operations",
                "coarse_merges",
                "supported_pairwise_interactions",
                "context_conditioned_structural_splits",
                "exact_cell_fine",
                "deterministic_hash_distractors",
            ],
            "minimum_interaction_cell_support": 2,
            "minimum_interaction_item_support": 3,
            "structural_split_rule": (
                "For each compositional parent, choose the dimension/value "
                "predicate with maximum minimum child cell support on seen "
                "grammar; ties are lexical; retain unsplittable parents."
            ),
            "hash_distractor_seed": 20260830,
            "hash_distractor_count": 18,
            "q_equivalence": "unordered activation columns on seen items",
        },
        "selection": {
            "learner_split": {
                "mode": "learner_disjoint_stable_hash",
                "validation_fraction": 0.20,
                "seed": 20260830,
            },
            "model": "observable_pfa_logistic",
            "features": [
                "learner_success_rate",
                "learner_log_attempts",
                "per_kc_active",
                "per_kc_prior_successes",
                "per_kc_prior_failures",
            ],
            "history_prior": {"alpha": 1.0, "beta": 1.0},
            "regularization_c": 0.1,
            "max_iterations": 300,
            "model_seed": 20260827,
            "objective": {
                "metric": "validation_log_loss",
                "complexity": "kc_count",
                "complexity_penalty": 0.0005,
                "minimum_improvement": 0.0,
            },
            "whole_policy_ids": [
                "atomic_features",
                "compositional_operations",
                "coarse_operations",
                "fine_exact_cells",
                "structural_splits",
                "compositional_plus_interactions",
                "hash_distractor_negative_control",
            ],
            "automated": {
                "protected_base": "atomic_features",
                "addition_families": ["operation", "interaction"],
                "forward_add": True,
                "backward_prune": True,
                "complexity_penalty": 0.0005,
                "preserve_all_seen_q_equivalent_projections": True,
            },
            "winner_rule": {
                "objective_tolerance": 1e-12,
                "retain_all_tied_policies": True,
                "operational_representative": (
                    "minimum SHA-256 of the name-free sorted Q-column signature; "
                    "this is not recovery evidence"
                ),
            },
        },
        "evaluation": {
            "probe_history_updates": False,
            "predictive_metrics": ["log_loss", "brier_score"],
            "grammar_regimes": [
                "seen",
                "unseen_combination",
                "unseen_value",
            ],
            "structural_metrics": [
                "optimal_activation_jaccard",
                "name_free_aligned_q_edge_precision_recall_f1",
                "exact_activation_recovery",
                "merge_split_missing_spurious_characterisation",
            ],
            "bootstrap": {
                "unit": "learner",
                "repeats": 2000,
                "seed": 20260830,
                "interval": 0.95,
            },
            "positive_control_interpretation": (
                "candidate-space structural reachability ceiling only"
            ),
            "negative_control": "hash_distractor_negative_control",
        },
        "inputs": {
            "selection_public": {
                name: {"path": _relative(path), "sha256": sha256_file(path)}
                for name, path in selection_inputs.items()
            },
            "evaluation_only_truth": {
                name: {"path": _relative(path), "sha256": sha256_file(path)}
                for name, path in evaluation_only_inputs.items()
            },
        },
        "implementation": {
            "path": _relative(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
        },
    }
    plan["plan_semantic_sha256"] = semantic_digest(plan)
    return plan


def _verify_plan(plan: dict[str, Any], *, include_truth: bool) -> None:
    digest = plan.get("plan_semantic_sha256")
    unsigned = {key: value for key, value in plan.items() if key != "plan_semantic_sha256"}
    if digest != semantic_digest(unsigned):
        raise ValueError("RQ3 plan semantic hash mismatch")
    if plan.get("study_id") != STUDY_ID or plan.get("plan_version") != PLAN_VERSION:
        raise ValueError("unexpected RQ3 plan identity")
    code = plan["implementation"]
    if sha256_file(_resolve(code["path"])) != code["sha256"]:
        raise ValueError("RQ3 implementation changed after the plan was frozen")
    groups = ["selection_public"]
    if include_truth:
        groups.append("evaluation_only_truth")
    for group in groups:
        for name, row in plan["inputs"][group].items():
            if sha256_file(_resolve(row["path"])) != row["sha256"]:
                raise ValueError(f"RQ3 {group} input changed after planning: {name}")


def _write_new_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen RQ3 artifact: {path}")
    write_json(path, value)


def _read_public_acquisition_events(
    path: Path, *, learner_count: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read only acquisition outcomes; probe ``correct`` is never accessed."""

    allowed_learners = {f"learner_{index:06d}" for index in range(1, learner_count + 1)}
    rows: list[dict[str, Any]] = []
    skipped_probe_rows = 0
    seen_raw_fields: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            raw = json.loads(line)
            if raw.get("learner_id") not in allowed_learners:
                continue
            seen_raw_fields.update(raw)
            if raw.get("phase") != "acquisition":
                skipped_probe_rows += 1
                continue
            if raw.get("grammar_regime") != "seen":
                raise ValueError("baseline acquisition contains non-seen grammar")
            forbidden = FORBIDDEN_SELECTION_TOKENS & set(raw)
            if forbidden:
                raise ValueError(f"observable interactions leak oracle fields: {sorted(forbidden)}")
            unknown = set(raw) - PUBLIC_EVENT_FIELDS
            if unknown:
                raise ValueError(f"selection received undeclared event fields: {sorted(unknown)}")
            rows.append(
                {
                    "event_id": (
                        f"{raw['learner_id']}__{int(raw['sequence_index']):04d}"
                    ),
                    "learner_id": raw["learner_id"],
                    "item_id": raw["item_id"],
                    "sequence_index": int(raw["sequence_index"]),
                    "correct": int(raw["correct"]),
                }
            )
    learners = sorted({row["learner_id"] for row in rows})
    if len(learners) != learner_count:
        raise ValueError(
            f"requested {learner_count} selection learners but found {len(learners)}"
        )
    return rows, {
        "acquisition_rows_read": len(rows),
        "learners": len(learners),
        "probe_rows_skipped_before_outcome_access": skipped_probe_rows,
        "probe_outcomes_read": False,
        "raw_event_fields_seen": sorted(seen_raw_fields),
    }


def selection_events_from_rows(
    rows: Iterable[dict[str, Any]], *, learner_ids: set[str]
) -> list[dict[str, Any]]:
    """Testable in-memory form of the no-probe selection boundary."""

    output = []
    for raw in rows:
        if raw.get("learner_id") not in learner_ids:
            continue
        if raw.get("phase") != "acquisition":
            continue
        if raw.get("grammar_regime") != "seen":
            raise ValueError("selection may only read seen acquisition rows")
        forbidden = FORBIDDEN_SELECTION_TOKENS & set(raw)
        if forbidden:
            raise ValueError(f"selection row leaks oracle fields: {sorted(forbidden)}")
        output.append(
            {
                "event_id": f"{raw['learner_id']}__{int(raw['sequence_index']):04d}",
                "learner_id": raw["learner_id"],
                "item_id": raw["item_id"],
                "sequence_index": int(raw["sequence_index"]),
                "correct": int(raw["correct"]),
            }
        )
    return output


def _rule_matches(features: dict[str, str], rule: dict[str, Any]) -> bool:
    if rule["kind"] == "activation":
        return activation_matches(features, rule["activation"])
    if rule["kind"] == "hash_threshold":
        ordered = json.dumps(features, sort_keys=True, separators=(",", ":"))
        return _stable_unit(rule["seed"], rule["index"], ordered) < float(
            rule["threshold"]
        )
    raise ValueError(f"unknown discovery rule kind: {rule['kind']}")


def _candidate_from_retained(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "family": row["family"],
        "definition": row["definition"],
        "rule": {"kind": "activation", "activation": row["activation"]},
        "selection_cell_support": int(row["cell_support"]),
        "selection_item_support": int(row["item_support"]),
        "supporting_selection_item_ids": list(row["supporting_development_item_ids"]),
    }


def _candidate_support(
    rule: dict[str, Any],
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    active_cells = {
        row["cell_id"] for row in cells if _rule_matches(row["features"], rule)
    }
    active_items = sorted(
        row["item_id"] for row in items if row["cell_id"] in active_cells
    )
    return sorted(active_cells), active_items


def _make_structural_splits(
    parents: list[dict[str, Any]],
    schema: dict[str, Any],
    seen_cells: list[dict[str, Any]],
    seen_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    children = []
    policy_ids = []
    for parent in parents:
        parent_cells = [
            cell
            for cell in seen_cells
            if _rule_matches(cell["features"], parent["rule"])
        ]
        trials = []
        for dimension in schema["dimension_order"]:
            for value in schema["dimensions"][dimension]["allowed_values"]:
                yes = sum(cell["features"][dimension] == value for cell in parent_cells)
                no = len(parent_cells) - yes
                if yes and no:
                    trials.append((min(yes, no), dimension, value, yes, no))
        if not trials:
            policy_ids.append(parent["id"])
            continue
        _balance, dimension, value, _yes, _no = sorted(
            trials, key=lambda row: (-row[0], row[1], row[2])
        )[0]
        for branch, expected in (("yes", value), ("no", {"not": value})):
            candidate_id = f"split__{parent['id']}__{dimension}__{value}__{branch}"
            activation = {
                "all": [
                    parent["rule"]["activation"],
                    {"cell": {dimension: expected}},
                ]
            }
            rule = {"kind": "activation", "activation": activation}
            support_cells, support_items = _candidate_support(
                rule, seen_cells, seen_items
            )
            if not support_items:
                raise AssertionError("balanced structural split produced an empty child")
            children.append(
                {
                    "id": candidate_id,
                    "family": "structural_split",
                    "definition": (
                        f"Context-conditioned child of {parent['id']} by "
                        f"{dimension} {branch} {value}."
                    ),
                    "rule": rule,
                    "parent_id": parent["id"],
                    "split_predicate": {
                        "dimension": dimension,
                        "value": value,
                        "branch": branch,
                    },
                    "selection_cell_support": len(support_cells),
                    "selection_item_support": len(support_items),
                    "supporting_selection_item_ids": support_items,
                }
            )
            policy_ids.append(candidate_id)
    return children, sorted(policy_ids)


def build_candidate_space(
    schema: dict[str, Any],
    all_cells: list[dict[str, Any]],
    all_items: list[dict[str, Any]],
    regimes: list[dict[str, Any]],
    candidate_design: dict[str, Any],
    operations: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Construct all hypotheses from public structure, using seen rows only."""

    regime_by_cell = {row["cell_id"]: row["grammar_regime"] for row in regimes}
    seen_cells = [row for row in all_cells if regime_by_cell[row["cell_id"]] == "seen"]
    seen_ids = {row["cell_id"] for row in seen_cells}
    seen_items = [row for row in all_items if row["cell_id"] in seen_ids]
    design = dict(candidate_design)
    design["operation_declarations"] = operations["operations"]
    retained = make_kc_candidates(schema, seen_cells, seen_items, design)
    candidates = [_candidate_from_retained(row) for row in retained["candidates"]]
    by_id = {row["id"]: row for row in candidates}

    atomic = sorted(
        row["id"]
        for row in retained["candidates"]
        if row["family"] == "feature_value" and row["selection_eligible"]
    )
    replacements = {
        "kc_feature__aspect__perfect": "kc_operation__perfect_dependency",
        "kc_feature__aspect__progressive": "kc_operation__progressive_dependency",
    }
    missing_replacements = set(replacements.values()) - set(by_id)
    if missing_replacements:
        raise ValueError(f"compositional candidates missing: {sorted(missing_replacements)}")
    compositional = sorted(replacements.get(candidate_id, candidate_id) for candidate_id in atomic)
    compositional_rows = [by_id[candidate_id] for candidate_id in compositional]

    coarse = sorted(
        {
            "kc_operation__finite_tense_form",
            "kc_operation__perfect_dependency",
            "kc_operation__progressive_dependency",
            "kc_operation__passive_dependency",
            "kc_operation__negation",
            "kc_operation__central_modal",
            "kc_operation__operator_inversion",
            "kc_operation__imperative",
        }
        & set(by_id)
    )
    interactions = sorted(
        row["id"]
        for row in retained["candidates"]
        if row["family"] == "interaction" and row["selection_eligible"]
    )
    full_cells = sorted(
        row["id"] for row in retained["candidates"] if row["family"] == "full_cell"
    )
    split_rows, split_ids = _make_structural_splits(
        compositional_rows, schema, seen_cells, seen_items
    )
    candidates.extend(split_rows)

    hash_rows = []
    hash_ids = []
    hash_seed = int(plan["candidate_space"]["hash_distractor_seed"])
    hash_count = int(plan["candidate_space"]["hash_distractor_count"])
    for index in range(hash_count):
        reference = by_id[atomic[index % len(atomic)]]
        density = reference["selection_cell_support"] / len(seen_cells)
        target_support = max(
            2,
            min(len(seen_cells) - 2, round(density * len(seen_cells))),
        )
        scores = sorted(
            _stable_unit(
                hash_seed,
                index,
                json.dumps(cell["features"], sort_keys=True, separators=(",", ":")),
            )
            for cell in seen_cells
        )
        # Midpoint gives exactly the outcome-free target support on seen cells;
        # the same universal hash rule projects without inspecting holdout rows.
        threshold = (scores[target_support - 1] + scores[target_support]) / 2
        candidate_id = f"hash_distractor_{index + 1:02d}"
        rule = {
            "kind": "hash_threshold",
            "seed": hash_seed,
            "index": index,
            "threshold": threshold,
        }
        support_cells, support_items = _candidate_support(rule, seen_cells, seen_items)
        if not support_items:
            raise ValueError(f"hash distractor has no seen support: {candidate_id}")
        hash_rows.append(
            {
                "id": candidate_id,
                "family": "hash_distractor",
                "definition": "Deterministic semantic-feature hash negative control.",
                "rule": rule,
                "selection_cell_support": len(support_cells),
                "selection_item_support": len(support_items),
                "supporting_selection_item_ids": support_items,
            }
        )
        hash_ids.append(candidate_id)
    candidates.extend(hash_rows)
    by_id = {row["id"]: row for row in candidates}
    if len(by_id) != len(candidates):
        raise ValueError("discovery candidate IDs are not unique")

    automated_additions = sorted(
        row["id"]
        for row in retained["candidates"]
        if row["family"] in {"operation", "interaction"}
        and row["selection_eligible"]
        and row["id"] not in atomic
    )
    policies = {
        "atomic_features": atomic,
        "compositional_operations": compositional,
        "coarse_operations": coarse,
        "fine_exact_cells": full_cells,
        "structural_splits": split_ids,
        "compositional_plus_interactions": sorted(compositional + interactions),
        "hash_distractor_negative_control": sorted(hash_ids),
    }
    expected = plan["selection"]["whole_policy_ids"]
    if list(policies) != expected:
        raise ValueError("implemented policy order differs from frozen plan")
    return {
        "candidate_space_id": "full_v1_public_structural_candidates_v1",
        "seen_cell_ids": sorted(seen_ids),
        "seen_item_ids": sorted(row["item_id"] for row in seen_items),
        "candidates": sorted(candidates, key=lambda row: row["id"]),
        "policies": policies,
        "automated": {
            "protected_base_ids": atomic,
            "equivalent_compositional_base_ids": compositional,
            "base_replacements": replacements,
            "eligible_addition_ids": automated_additions,
        },
        "metadata": {
            "learner_outcomes_read": False,
            "probe_outcomes_read": False,
            "generator_kcs_read": False,
            "true_q_read": False,
            "oracle_truth_read": False,
            "heldout_cell_features_read_during_candidate_construction": False,
            "all_item_projection_deferred_until_after_selection": True,
            "retained_candidate_counts": retained["candidate_counts"],
        },
    }


def _learner_partition(
    events: list[dict[str, Any]], split: dict[str, Any]
) -> tuple[set[str], set[str]]:
    learners = sorted({row["learner_id"] for row in events})
    ranked = sorted(
        learners,
        key=lambda learner: (
            _stable_unit(split["seed"], learner),
            learner,
        ),
    )
    validation_count = max(1, round(len(ranked) * float(split["validation_fraction"])))
    if validation_count >= len(ranked):
        raise ValueError("learner partition requires train and validation learners")
    validation = set(ranked[:validation_count])
    return set(ranked[validation_count:]), validation


def build_observable_history_matrix(
    events: list[dict[str, Any]],
    candidate_ids: list[str],
    supporting_items: dict[str, set[str]],
    *,
    alpha: float,
    beta: float,
    update_field: str | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build retained-selector-equivalent PFA histories from strictly prior rows."""

    candidate_ids = list(candidate_ids)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("history candidate IDs contain duplicates")
    candidate_index = {candidate_id: index for index, candidate_id in enumerate(candidate_ids)}
    active_by_item: dict[str, np.ndarray] = {}
    item_ids = {row["item_id"] for row in events}
    for item_id in item_ids:
        active_by_item[item_id] = np.asarray(
            [
                candidate_index[candidate_id]
                for candidate_id in candidate_ids
                if item_id in supporting_items[candidate_id]
            ],
            dtype=np.int32,
        )
    ordered = sorted(
        enumerate(events),
        key=lambda pair: (pair[1]["learner_id"], pair[1]["sequence_index"]),
    )
    x = np.zeros((len(events), 2 + 3 * len(candidate_ids)), dtype=np.float32)
    y = np.empty(len(events), dtype=np.int8)
    learners = [""] * len(events)
    current_learner = None
    learner_attempts = 0
    learner_correct = 0
    kc_attempts = np.zeros(len(candidate_ids), dtype=np.int32)
    kc_correct = np.zeros(len(candidate_ids), dtype=np.int32)
    for original_index, event in ordered:
        learner = event["learner_id"]
        if learner != current_learner:
            current_learner = learner
            learner_attempts = 0
            learner_correct = 0
            kc_attempts.fill(0)
            kc_correct.fill(0)
        active = active_by_item[event["item_id"]]
        x[original_index, 0] = (learner_correct + alpha) / (
            learner_attempts + alpha + beta
        )
        x[original_index, 1] = math.log1p(learner_attempts)
        if len(active):
            base = 2 + 3 * active
            x[original_index, base] = 1.0
            x[original_index, base + 1] = kc_correct[active]
            x[original_index, base + 2] = kc_attempts[active] - kc_correct[active]
        y[original_index] = int(event["correct"])
        learners[original_index] = learner
        updates = True if update_field is None else bool(event.get(update_field, False))
        if updates:
            learner_attempts += 1
            learner_correct += int(event["correct"])
            kc_attempts[active] += 1
            kc_correct[active] += int(event["correct"])
    return x, y, learners


def _candidate_columns(
    all_candidate_ids: list[str], selected_ids: list[str]
) -> list[int]:
    index = {candidate_id: position for position, candidate_id in enumerate(all_candidate_ids)}
    columns = [0, 1]
    for candidate_id in selected_ids:
        position = index[candidate_id]
        columns.extend([2 + 3 * position, 3 + 3 * position, 4 + 3 * position])
    return columns


def _fit_score(
    x: np.ndarray,
    y: np.ndarray,
    learners: list[str],
    train_learners: set[str],
    validation_learners: set[str],
    columns: list[int],
    design: dict[str, Any],
) -> tuple[dict[str, Any], np.ndarray]:
    train_mask = np.fromiter((learner in train_learners for learner in learners), bool)
    validation_mask = np.fromiter(
        (learner in validation_learners for learner in learners), bool
    )
    matrix = np.asarray(x[:, columns], dtype=np.float32, order="C")
    scaler = StandardScaler(copy=False)
    train_x = scaler.fit_transform(matrix[train_mask])
    matrix = scaler.transform(matrix, copy=False)
    train_y = y[train_mask]
    if len(np.unique(train_y)) != 2:
        raise ValueError("observable selector training outcomes require both classes")
    model = LogisticRegression(
        C=float(design["regularization_c"]),
        max_iter=int(design["max_iterations"]),
        random_state=int(design["model_seed"]),
    )
    model.fit(train_x, train_y)
    probability = np.clip(model.predict_proba(matrix)[:, 1], 1e-6, 1 - 1e-6)
    target = y[validation_mask].astype(float)
    predicted = probability[validation_mask]
    return {
        "validation_events": int(validation_mask.sum()),
        "validation_log_loss": float(
            np.mean(-(target * np.log(predicted) + (1 - target) * np.log(1 - predicted)))
        ),
        "validation_brier_score": float(np.mean((predicted - target) ** 2)),
    }, probability


def _q_signature(
    policy_ids: list[str], supporting_items: dict[str, set[str]], item_ids: list[str]
) -> str:
    columns = []
    for candidate_id in policy_ids:
        active = supporting_items[candidate_id]
        columns.append("".join("1" if item_id in active else "0" for item_id in item_ids))
    return semantic_digest(sorted(columns))


def _score_fixed_policy(
    events: list[dict[str, Any]],
    candidate_ids: list[str],
    supporting_items: dict[str, set[str]],
    train_learners: set[str],
    validation_learners: set[str],
    selection: dict[str, Any],
) -> dict[str, Any]:
    x, y, learners = build_observable_history_matrix(
        events,
        candidate_ids,
        supporting_items,
        alpha=float(selection["history_prior"]["alpha"]),
        beta=float(selection["history_prior"]["beta"]),
    )
    metrics, _ = _fit_score(
        x,
        y,
        learners,
        train_learners,
        validation_learners,
        list(range(x.shape[1])),
        selection,
    )
    penalty = float(selection["objective"]["complexity_penalty"])
    return {
        **metrics,
        "kc_count": len(candidate_ids),
        "complexity_penalty": penalty * len(candidate_ids),
        "objective": metrics["validation_log_loss"] + penalty * len(candidate_ids),
    }


def _run_forward_selector(
    events: list[dict[str, Any]],
    base_ids: list[str],
    addition_ids: list[str],
    supporting_items: dict[str, set[str]],
    train_learners: set[str],
    validation_learners: set[str],
    selection: dict[str, Any],
) -> dict[str, Any]:
    all_ids = sorted(set(base_ids + addition_ids))
    x, y, learners = build_observable_history_matrix(
        events,
        all_ids,
        supporting_items,
        alpha=float(selection["history_prior"]["alpha"]),
        beta=float(selection["history_prior"]["beta"]),
    )
    penalty = float(selection["objective"]["complexity_penalty"])
    cache: dict[tuple[str, ...], dict[str, Any]] = {}

    def score(ids: list[str]) -> dict[str, Any]:
        key = tuple(sorted(ids))
        if key not in cache:
            metrics, _ = _fit_score(
                x,
                y,
                learners,
                train_learners,
                validation_learners,
                _candidate_columns(all_ids, list(key)),
                selection,
            )
            cache[key] = {
                **metrics,
                "kc_count": len(key),
                "complexity_penalty": penalty * len(key),
                "objective": metrics["validation_log_loss"] + penalty * len(key),
            }
        return cache[key]

    selected = sorted(base_ids)
    current = score(selected)
    trace = [{"step": 0, "action": "initial_feature_base", "score": current}]
    remaining = sorted(addition_ids)
    while remaining:
        trials = []
        for candidate_id in remaining:
            trial = score(selected + [candidate_id])
            trials.append(
                {
                    "candidate_id": candidate_id,
                    "score": trial,
                    "objective_improvement": current["objective"] - trial["objective"],
                }
            )
        best = sorted(
            trials, key=lambda row: (-row["objective_improvement"], row["candidate_id"])
        )[0]
        if best["objective_improvement"] <= float(
            selection["objective"]["minimum_improvement"]
        ):
            trace.append(
                {
                    "step": len(trace),
                    "action": "forward_stop",
                    "best_rejected": best,
                    "candidate_scores": trials,
                }
            )
            break
        selected.append(best["candidate_id"])
        selected.sort()
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
    for candidate_id in reversed([row for row in selected if row not in set(base_ids)]):
        trial_ids = [row for row in selected if row != candidate_id]
        trial = score(trial_ids)
        if trial["objective"] <= current["objective"]:
            selected = trial_ids
            current = trial
            trace.append(
                {
                    "step": len(trace),
                    "action": "backward_prune",
                    "pruned": candidate_id,
                    "score": current,
                }
            )
    return {
        "selected_candidate_ids": sorted(selected),
        "final_score": current,
        "trace": trace,
        "unique_policy_scores_cached": len(cache),
        "feature_matrix": {
            "rows": int(x.shape[0]),
            "candidate_columns": len(all_ids),
            "numeric_columns": int(x.shape[1]),
            "dtype": str(x.dtype),
        },
    }


def run_selection(plan: dict[str, Any], *, cohort: str) -> dict[str, Any]:
    """Run selection.  Its signature intentionally contains no truth inputs."""

    _verify_plan(plan, include_truth=False)
    if cohort not in plan["cohorts"]:
        raise ValueError(f"unknown RQ3 cohort: {cohort}")
    paths = {
        name: _resolve(row["path"])
        for name, row in plan["inputs"]["selection_public"].items()
    }
    schema = read_yaml(paths["grammar_schema"])
    cells = read_jsonl(paths["cells"])
    items = read_jsonl(paths["items"])
    regimes = read_jsonl(paths["regimes"])
    candidate_space = build_candidate_space(
        schema,
        cells,
        items,
        regimes,
        read_yaml(paths["candidate_design"]),
        read_yaml(paths["operation_declarations"]),
        plan,
    )
    events, event_audit = _read_public_acquisition_events(
        paths["interactions"],
        learner_count=int(plan["cohorts"][cohort]["learners"]),
    )
    seen_item_ids = set(candidate_space["seen_item_ids"])
    unknown = {row["item_id"] for row in events} - seen_item_ids
    if unknown:
        raise ValueError(f"selection acquisition has unknown seen items: {sorted(unknown)}")
    selection = plan["selection"]
    train_learners, validation_learners = _learner_partition(
        events, selection["learner_split"]
    )
    candidates = {row["id"]: row for row in candidate_space["candidates"]}
    supporting_items = {
        candidate_id: set(row["supporting_selection_item_ids"])
        for candidate_id, row in candidates.items()
    }
    policy_scores = {}
    for policy_id, candidate_ids in candidate_space["policies"].items():
        policy_scores[policy_id] = _score_fixed_policy(
            events,
            candidate_ids,
            supporting_items,
            train_learners,
            validation_learners,
            selection,
        )
    automated = _run_forward_selector(
        events,
        candidate_space["automated"]["protected_base_ids"],
        candidate_space["automated"]["eligible_addition_ids"],
        supporting_items,
        train_learners,
        validation_learners,
        selection,
    )
    automated_atomic = automated["selected_candidate_ids"]
    replacements = candidate_space["automated"]["base_replacements"]
    automated_compositional = sorted(
        replacements.get(candidate_id, candidate_id) for candidate_id in automated_atomic
    )
    candidate_space["policies"]["automated_atomic_projection"] = automated_atomic
    candidate_space["policies"]["automated_compositional_projection"] = automated_compositional
    policy_scores["automated_atomic_projection"] = automated["final_score"]
    policy_scores["automated_compositional_projection"] = automated["final_score"]

    item_order = candidate_space["seen_item_ids"]
    signatures = {
        policy_id: _q_signature(candidate_ids, supporting_items, item_order)
        for policy_id, candidate_ids in candidate_space["policies"].items()
    }
    equivalence: dict[str, list[str]] = defaultdict(list)
    for policy_id, signature in signatures.items():
        equivalence[signature].append(policy_id)
    equivalence_classes = [
        {
            "seen_q_signature": signature,
            "policy_ids": sorted(policy_ids),
            "observationally_distinguishable_on_seen_q": False,
        }
        for signature, policy_ids in sorted(equivalence.items())
        if len(policy_ids) > 1
    ]
    best_objective = min(row["objective"] for row in policy_scores.values())
    tolerance = float(selection["winner_rule"]["objective_tolerance"])
    best_policy_ids = sorted(
        policy_id
        for policy_id, score in policy_scores.items()
        if score["objective"] <= best_objective + tolerance
    )
    best_signatures = sorted({signatures[policy_id] for policy_id in best_policy_ids})
    operational_signature = min(best_signatures)
    operational_ids = sorted(
        policy_id
        for policy_id in best_policy_ids
        if signatures[policy_id] == operational_signature
    )
    result = {
        "study_id": STUDY_ID,
        "artifact_type": "FROZEN_OBSERVABLE_SELECTION",
        "cohort": cohort,
        "cohort_status": plan["cohorts"][cohort]["status"],
        "plan_semantic_sha256": plan["plan_semantic_sha256"],
        "candidate_space": candidate_space,
        "selection": {
            "policy_scores": policy_scores,
            "automated_forward_selector": automated,
            "best_objective": best_objective,
            "best_policy_ids": best_policy_ids,
            "best_seen_q_signatures": best_signatures,
            "operational_signature_by_name_free_hash": operational_signature,
            "operational_policy_ids_with_same_signature": operational_ids,
            "unique_recovery_claimed": False,
            "observed_q_equivalence_classes": equivalence_classes,
            "learner_partition": {
                "train_learners": len(train_learners),
                "validation_learners": len(validation_learners),
                "train_learner_ids_sha256": semantic_digest(sorted(train_learners)),
                "validation_learner_ids_sha256": semantic_digest(
                    sorted(validation_learners)
                ),
            },
        },
        "boundary_audit": {
            **event_audit,
            "selection_input_groups_read": ["selection_public"],
            "evaluation_truth_input_group_read": False,
            "generator_kcs_read": False,
            "true_q_read": False,
            "oracle_truth_read": False,
            "probe_outcomes_read": False,
            "reserved_probe_outcomes_influenced_selection": False,
        },
    }
    result["selection_semantic_sha256"] = semantic_digest(result)
    return result


def project_policy(
    items: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    candidate_ids: list[str],
) -> list[dict[str, Any]]:
    """Mechanically project a frozen public candidate policy to every item."""

    by_cell = {row["cell_id"]: row["features"] for row in cells}
    output = []
    for item in items:
        features = by_cell[item["cell_id"]]
        output.append(
            {
                "item_id": item["item_id"],
                "cell_id": item["cell_id"],
                "kc_ids": [
                    candidate_id
                    for candidate_id in candidate_ids
                    if _rule_matches(features, candidates[candidate_id]["rule"])
                ],
            }
        )
    if len(output) != len(items):
        raise AssertionError("frozen policy failed to project every item")
    return output


def _binary_columns(
    item_ids: list[str], projection: dict[str, set[str]], kc_ids: list[str]
) -> np.ndarray:
    return np.asarray(
        [[int(kc_id in projection[item_id]) for kc_id in kc_ids] for item_id in item_ids],
        dtype=np.int8,
    )


def structural_recovery_metrics(
    true_projection: dict[str, set[str]],
    predicted_projection: dict[str, set[str]],
    *,
    item_ids: list[str],
) -> dict[str, Any]:
    """Compare activation columns without relying on KC labels."""

    true_ids = sorted({kc for item in item_ids for kc in true_projection[item]})
    predicted_ids = sorted(
        {kc for item in item_ids for kc in predicted_projection[item]}
    )
    true_q = _binary_columns(item_ids, true_projection, true_ids)
    predicted_q = _binary_columns(item_ids, predicted_projection, predicted_ids)
    similarities = np.zeros((len(true_ids), len(predicted_ids)), dtype=float)
    for i in range(len(true_ids)):
        left = true_q[:, i].astype(bool)
        for j in range(len(predicted_ids)):
            right = predicted_q[:, j].astype(bool)
            union = int(np.logical_or(left, right).sum())
            similarities[i, j] = (
                float(np.logical_and(left, right).sum() / union) if union else 1.0
            )
    if len(true_ids) and len(predicted_ids):
        true_index, predicted_index = linear_sum_assignment(-similarities)
        matches = list(zip(true_index.tolist(), predicted_index.tolist(), strict=True))
    else:
        matches = []
    matched_true = {left for left, _right in matches}
    matched_predicted = {right for _left, right in matches}
    tp = fp = fn = 0
    matching_rows = []
    for left, right in matches:
        true_col = true_q[:, left].astype(bool)
        predicted_col = predicted_q[:, right].astype(bool)
        tp += int(np.logical_and(true_col, predicted_col).sum())
        fp += int(np.logical_and(~true_col, predicted_col).sum())
        fn += int(np.logical_and(true_col, ~predicted_col).sum())
        matching_rows.append(
            {
                "true_kc_id": true_ids[left],
                "predicted_kc_id": predicted_ids[right],
                "activation_jaccard": float(similarities[left, right]),
            }
        )
    for left in set(range(len(true_ids))) - matched_true:
        fn += int(true_q[:, left].sum())
    for right in set(range(len(predicted_ids))) - matched_predicted:
        fp += int(predicted_q[:, right].sum())
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    true_sets = [set(np.flatnonzero(true_q[:, index])) for index in range(len(true_ids))]
    pred_sets = [
        set(np.flatnonzero(predicted_q[:, index])) for index in range(len(predicted_ids))
    ]
    exact_pairs = [
        {"true_kc_id": true_ids[i], "predicted_kc_id": predicted_ids[j]}
        for i, left in enumerate(true_sets)
        for j, right in enumerate(pred_sets)
        if left and left == right
    ]
    merge_rows = []
    for j, predicted in enumerate(pred_sets):
        contained = [i for i, true in enumerate(true_sets) if true and true <= predicted]
        exact_union = [i for i in contained if true_sets[i] != predicted]
        if len(exact_union) >= 2 and set().union(*(true_sets[i] for i in exact_union)) == predicted:
            merge_rows.append(
                {
                    "predicted_kc_id": predicted_ids[j],
                    "merged_true_kc_ids": [true_ids[i] for i in exact_union],
                }
            )
    split_rows = []
    for i, true in enumerate(true_sets):
        strict_parts = [j for j, predicted in enumerate(pred_sets) if predicted and predicted < true]
        if len(strict_parts) >= 2 and set().union(*(pred_sets[j] for j in strict_parts)) == true:
            split_rows.append(
                {
                    "true_kc_id": true_ids[i],
                    "split_predicted_kc_ids": [predicted_ids[j] for j in strict_parts],
                }
            )
    zero_overlap_true = [
        true_ids[i]
        for i in range(len(true_ids))
        if not len(predicted_ids) or float(similarities[i].max()) == 0.0
    ]
    spurious = [
        predicted_ids[j]
        for j in range(len(predicted_ids))
        if not len(true_ids) or float(similarities[:, j].max()) == 0.0
    ]
    denominator = max(len(true_ids), len(predicted_ids), 1)
    return {
        "items": len(item_ids),
        "true_kcs": len(true_ids),
        "predicted_kcs": len(predicted_ids),
        "optimal_matching": {
            "matched_pairs": matching_rows,
            "mean_activation_jaccard_padded": float(
                sum(row["activation_jaccard"] for row in matching_rows) / denominator
            ),
            "true_mean_best_jaccard": float(
                np.mean(similarities.max(axis=1))
                if len(true_ids) and len(predicted_ids)
                else 0.0
            ),
            "predicted_mean_best_jaccard": float(
                np.mean(similarities.max(axis=0))
                if len(true_ids) and len(predicted_ids)
                else 0.0
            ),
        },
        "aligned_q_edges": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "characterisation": {
            "exact_activation_pairs": exact_pairs,
            "exact_true_kcs_recovered": len({row["true_kc_id"] for row in exact_pairs}),
            "merge_candidates": merge_rows,
            "split_true_kcs": split_rows,
            "zero_overlap_missing_true_kc_ids": zero_overlap_true,
            "spurious_zero_overlap_predicted_kc_ids": spurious,
            "unique_exact_recovery": (
                len(true_ids) == len(predicted_ids)
                and len({row["true_kc_id"] for row in exact_pairs}) == len(true_ids)
                and len({row["predicted_kc_id"] for row in exact_pairs}) == len(predicted_ids)
            ),
        },
    }


def _read_all_observable_events(
    path: Path, *, learner_count: int
) -> list[dict[str, Any]]:
    allowed = {f"learner_{index:06d}" for index in range(1, learner_count + 1)}
    output = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            raw = json.loads(line)
            if raw.get("learner_id") not in allowed:
                continue
            if set(raw) - PUBLIC_EVENT_FIELDS:
                raise ValueError("evaluation observable interactions contain unknown fields")
            output.append(
                {
                    "event_id": f"{raw['learner_id']}__{int(raw['sequence_index']):04d}",
                    "learner_id": raw["learner_id"],
                    "item_id": raw["item_id"],
                    "sequence_index": int(raw["sequence_index"]),
                    "correct": int(raw["correct"]),
                    "phase": raw["phase"],
                    "grammar_regime": raw["grammar_regime"],
                    "updates_history": raw["phase"] == "acquisition",
                }
            )
    return output


def _predictive_evaluation(
    events: list[dict[str, Any]],
    projection: list[dict[str, Any]],
    selection: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, float]]:
    candidate_ids = sorted({kc for row in projection for kc in row["kc_ids"]})
    supporting = {
        candidate_id: {
            row["item_id"] for row in projection if candidate_id in row["kc_ids"]
        }
        for candidate_id in candidate_ids
    }
    x, y, learners = build_observable_history_matrix(
        events,
        candidate_ids,
        supporting,
        alpha=float(selection["history_prior"]["alpha"]),
        beta=float(selection["history_prior"]["beta"]),
        update_field="updates_history",
    )
    train_mask = np.fromiter((row["phase"] == "acquisition" for row in events), bool)
    matrix = np.asarray(x, dtype=np.float32, order="C")
    scaler = StandardScaler(copy=False)
    train_x = scaler.fit_transform(matrix[train_mask])
    matrix = scaler.transform(matrix, copy=False)
    model = LogisticRegression(
        C=float(selection["regularization_c"]),
        max_iter=int(selection["max_iterations"]),
        random_state=int(selection["model_seed"]),
    )
    model.fit(train_x, y[train_mask])
    probability = np.clip(model.predict_proba(matrix)[:, 1], 1e-6, 1 - 1e-6)
    groups = {"all_probes": np.fromiter((row["phase"] == "probe" for row in events), bool)}
    for regime in ("seen", "unseen_combination", "unseen_value"):
        groups[regime] = np.fromiter(
            (row["phase"] == "probe" and row["grammar_regime"] == regime for row in events),
            bool,
        )
    metrics = {}
    for name, mask in groups.items():
        target = y[mask].astype(float)
        predicted = probability[mask]
        metrics[name] = {
            "n": int(mask.sum()),
            "log_loss": float(
                np.mean(-(target * np.log(predicted) + (1 - target) * np.log(1 - predicted)))
            ),
            "brier_score": float(np.mean((predicted - target) ** 2)),
        }
    probe_losses = {
        event["event_id"]: float(
            -(float(y[index]) * math.log(probability[index]) + (1 - float(y[index])) * math.log(1 - probability[index]))
        )
        for index, event in enumerate(events)
        if event["phase"] == "probe"
    }
    return metrics, probe_losses


def _paired_bootstrap(
    events: list[dict[str, Any]],
    reference: dict[str, float],
    candidate: dict[str, float],
    design: dict[str, Any],
) -> dict[str, Any]:
    losses: dict[str, list[float]] = defaultdict(list)
    for event in events:
        event_id = event["event_id"]
        if event_id in reference:
            losses[event["learner_id"]].append(candidate[event_id] - reference[event_id])
    learner_ids = sorted(losses)
    values = np.asarray([np.mean(losses[learner]) for learner in learner_ids])
    rng = np.random.default_rng(int(design["seed"]))
    samples = np.empty(int(design["repeats"]), dtype=float)
    for index in range(len(samples)):
        samples[index] = np.mean(rng.choice(values, size=len(values), replace=True))
    alpha = (1 - float(design["interval"])) / 2
    return {
        "unit": "learner",
        "learners": len(values),
        "candidate_minus_reference_mean_log_loss": float(values.mean()),
        "confidence_interval": [
            float(np.quantile(samples, alpha)),
            float(np.quantile(samples, 1 - alpha)),
        ],
        "repeats": len(samples),
        "seed": int(design["seed"]),
    }


def run_evaluation(
    plan: dict[str, Any], selection_result: dict[str, Any], *, cohort: str
) -> dict[str, Any]:
    """Evaluate only after verifying a frozen observable-selection artifact."""

    _verify_plan(plan, include_truth=True)
    if selection_result.get("artifact_type") != "FROZEN_OBSERVABLE_SELECTION":
        raise ValueError("RQ3 evaluation requires a frozen selection artifact")
    expected_digest = selection_result.get("selection_semantic_sha256")
    unsigned = {
        key: value
        for key, value in selection_result.items()
        if key != "selection_semantic_sha256"
    }
    if expected_digest != semantic_digest(unsigned):
        raise ValueError("RQ3 frozen selection artifact hash mismatch")
    if selection_result["cohort"] != cohort:
        raise ValueError("RQ3 selection/evaluation cohort mismatch")
    public_paths = {
        name: _resolve(row["path"])
        for name, row in plan["inputs"]["selection_public"].items()
    }
    truth_paths = {
        name: _resolve(row["path"])
        for name, row in plan["inputs"]["evaluation_only_truth"].items()
    }
    cells = read_jsonl(public_paths["cells"])
    items = read_jsonl(public_paths["items"])
    regimes = read_jsonl(public_paths["regimes"])
    regime_by_cell = {row["cell_id"]: row["grammar_regime"] for row in regimes}
    candidates = {
        row["id"]: row for row in selection_result["candidate_space"]["candidates"]
    }
    policies = selection_result["candidate_space"]["policies"]
    true_rows = read_jsonl(truth_paths["true_q_sparse"])
    true_projection = {
        row["item_id"]: set(row["generator_kc_ids"]) for row in true_rows
    }
    if set(true_projection) != {row["item_id"] for row in items}:
        raise ValueError("Q* and item bank differ")
    # Loading generator_kcs is evaluation-only and verifies declared truth columns.
    generator_ids = {row["id"] for row in read_jsonl(truth_paths["generator_kcs"])}
    if generator_ids != set().union(*true_projection.values()):
        raise ValueError("generator KC inventory and Q* columns differ")
    item_scopes = {
        "all": sorted(true_projection),
        "seen": sorted(
            row["item_id"]
            for row in items
            if regime_by_cell[row["cell_id"]] == "seen"
        ),
        "unseen_combination": sorted(
            row["item_id"]
            for row in items
            if regime_by_cell[row["cell_id"]] == "unseen_combination"
        ),
        "unseen_value": sorted(
            row["item_id"]
            for row in items
            if regime_by_cell[row["cell_id"]] == "unseen_value"
        ),
    }
    projections = {}
    structural = {}
    for policy_id, candidate_ids in policies.items():
        projection_rows = project_policy(items, cells, candidates, candidate_ids)
        predicted = {row["item_id"]: set(row["kc_ids"]) for row in projection_rows}
        projections[policy_id] = projection_rows
        structural[policy_id] = {
            scope: structural_recovery_metrics(
                true_projection, predicted, item_ids=item_ids
            )
            for scope, item_ids in item_scopes.items()
        }
    ceiling_ids = [
        policy_id
        for policy_id, result in structural.items()
        if result["all"]["characterisation"]["unique_exact_recovery"]
    ]
    events = _read_all_observable_events(
        public_paths["interactions"],
        learner_count=int(plan["cohorts"][cohort]["learners"]),
    )
    predictive = {}
    probe_losses = {}
    for policy_id, projection in projections.items():
        predictive[policy_id], probe_losses[policy_id] = _predictive_evaluation(
            events, projection, plan["selection"]
        )
    comparisons = {}
    reference_id = "compositional_operations"
    for policy_id in sorted(predictive):
        if policy_id == reference_id:
            continue
        comparisons[f"{policy_id}_minus_{reference_id}"] = _paired_bootstrap(
            events,
            probe_losses[reference_id],
            probe_losses[policy_id],
            plan["evaluation"]["bootstrap"],
        )
    best_ids = selection_result["selection"]["best_policy_ids"]
    exact_best = [
        policy_id
        for policy_id in best_ids
        if structural[policy_id]["all"]["characterisation"]["unique_exact_recovery"]
    ]
    result = {
        "study_id": STUDY_ID,
        "artifact_type": "POST_SELECTION_TRUTH_EVALUATION",
        "cohort": cohort,
        "cohort_status": plan["cohorts"][cohort]["status"],
        "plan_semantic_sha256": plan["plan_semantic_sha256"],
        "selection_semantic_sha256": selection_result["selection_semantic_sha256"],
        "structural_recovery": structural,
        "predictive_probe_evaluation": predictive,
        "learner_paired_probe_comparisons": comparisons,
        "interpretation_ledger": {
            "candidate_space_structural_ceiling_policy_ids": sorted(ceiling_ids),
            "ceiling_is_not_learner_evidence_recovery": True,
            "best_predictive_policy_ids": best_ids,
            "best_predictive_exact_recovery_policy_ids": exact_best,
            "unique_recovery_supported": len(best_ids) == 1 and len(exact_best) == 1,
            "predictively_equivalent_distinct_projections": selection_result["selection"]
            ["observed_q_equivalence_classes"],
            "primary_caveat": (
                "Seen-response prediction cannot choose among hypotheses with "
                "identical seen Q columns; holdout truth is used only to expose, "
                "not resolve, that ambiguity."
            ),
        },
        "boundary_audit": {
            "selection_frozen_before_truth_load": True,
            "probe_outcomes_used_for_selection": False,
            "probe_outcomes_used_for_model_fitting": False,
            "probe_outcomes_used_for_final_evaluation_only": True,
            "oracle_learner_truth_read": False,
            "generator_truth_read_after_selection_only": True,
            "all_probes_non_updating": all(
                not row["updates_history"] for row in events if row["phase"] == "probe"
            ),
        },
    }
    result["evaluation_semantic_sha256"] = semantic_digest(result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    plan_parser.add_argument("--output", type=Path, required=True)
    for command in ("select", "evaluate"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--plan", type=Path, required=True)
        sub.add_argument("--cohort", choices=("pilot", "final"), required=True)
        sub.add_argument("--output", type=Path, required=True)
        if command == "evaluate":
            sub.add_argument("--selection", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "plan":
        result = make_plan(args.dataset)
    else:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        if args.command == "select":
            result = run_selection(plan, cohort=args.cohort)
        else:
            selection = json.loads(args.selection.read_text(encoding="utf-8"))
            result = run_evaluation(plan, selection, cohort=args.cohort)
    _write_new_json(args.output, result)
    print(json.dumps({
        "status": result["artifact_type"] if "artifact_type" in result else result["status"],
        "output": _relative(args.output),
        "sha256": sha256_file(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
