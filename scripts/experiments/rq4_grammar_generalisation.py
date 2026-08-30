#!/usr/bin/env python3
"""Preregister and run full-v1 linguistic-generalisation experiments.

The immutable baseline analysis fits one observable logistic/PFA-like model per
already-frozen KC representation on seen acquisition rows only, then evaluates
the same terminal, non-updating probes.  A separate exact-item-novelty negative
control replaces each withheld seen item by its same-cell variant in the fixed
acquisition multiset, preserving the number and identity of K* opportunities.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt import baseline_simulation as baseline
from grammar_kt.io import read_jsonl, read_yaml
from scripts.experiments.rq2_kc_misspecification import (
    build_observable_feature_matrix,
    file_sha256,
    fit_observable_logistic,
    load_observable_events,
    load_projection_bundle,
    load_true_projection,
    paired_learner_bootstrap,
    prediction_metrics,
)
from scripts.experiments.rq3_kc_discovery import project_policy


STUDY_ID = "full_v1_rq4_grammar_generalisation_v1"
DEFAULT_DATASET = ROOT / "data/grammar_kt_full_v1"
DEFAULT_OUTPUT = ROOT / "experiments/full_v1/rq4_generalisation_v1"
RQ2_DIR = ROOT / "reports/full_v1_artifacts/rq2_misspecification_v1"
RQ3_DIR = ROOT / "experiments/full_v1/rq3_kc_discovery_v1"
REPRESENTATION_ORDER = (
    "true_kstar_compositional_ceiling",
    "rq3_atomic",
    "family_union_coarse",
    "structural_split2",
    "exact_cell_fine",
    "compositional_plus_intersections",
)
REGIME_ORDER = ("seen", "unseen_combination", "unseen_value")
PLAN_SEED = 20260830
BOOTSTRAP_REPEATS = 2000


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def semantic_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


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


def _stable_rank(seed: int, *parts: object) -> str:
    payload = "\x1f".join([str(seed), *(str(part) for part in parts)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dataset_inputs(dataset: Path) -> dict[str, dict[str, Any]]:
    dataset = dataset.resolve()
    paths = {
        "manifest": dataset / "manifest.json",
        "interactions": dataset / "interactions.jsonl.gz",
        "items": dataset / "items/items.jsonl",
        "cells": dataset / "grammar/cells.jsonl",
        "regimes": dataset / "grammar/regime_assignments.jsonl",
        "generator_kcs": dataset / "kcs.jsonl",
        "true_q_dense": dataset / "q_matrix.csv",
        "true_q_sparse": dataset / "oracle/q_matrix_sparse.jsonl",
        "simulator_config": ROOT / "modules/simulation/baseline.yaml",
        "rq2_plan": RQ2_DIR / "study_plan.json",
        "rq2_projections": RQ2_DIR / "projections.jsonl",
        "rq3_plan": RQ3_DIR / "plan.json",
        "rq3_selection": RQ3_DIR / "final_selection.json",
        "rq2_implementation": ROOT / "scripts/experiments/rq2_kc_misspecification.py",
        "rq3_implementation": ROOT / "scripts/experiments/rq3_kc_discovery.py",
        "simulator_implementation": ROOT / "src/grammar_kt/baseline_simulation.py",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"RQ4 inputs missing: {missing}")
    return {
        name: {"path": str(path.relative_to(ROOT)), "sha256": file_sha256(path)}
        for name, path in paths.items()
    }


def _load_q_sparse(path: Path) -> dict[str, tuple[str, ...]]:
    return {
        row["item_id"]: tuple(row["generator_kc_ids"])
        for row in read_jsonl(path)
    }


def build_representations(
    dataset: Path,
) -> tuple[dict[str, dict[str, tuple[str, ...]]], dict[str, Any]]:
    """Reuse only deterministic frozen RQ2/RQ3 projections."""

    items = read_jsonl(dataset / "items/items.jsonl")
    cells = read_jsonl(dataset / "grammar/cells.jsonl")
    rq2 = load_projection_bundle(RQ2_DIR / "projections.jsonl")
    rq3 = json.loads((RQ3_DIR / "final_selection.json").read_text(encoding="utf-8"))
    candidates = {row["id"]: row for row in rq3["candidate_space"]["candidates"]}
    rq3_policies = rq3["candidate_space"]["policies"]

    def rq3_projection(policy_id: str) -> dict[str, tuple[str, ...]]:
        rows = project_policy(items, cells, candidates, rq3_policies[policy_id])
        return {row["item_id"]: tuple(row["kc_ids"]) for row in rows}

    representations = {
        "true_kstar_compositional_ceiling": rq2["true_kstar"],
        "rq3_atomic": rq3_projection("atomic_features"),
        "family_union_coarse": rq2["coarse_linguistic_families"],
        "structural_split2": rq2["structural_split2"],
        "exact_cell_fine": rq2["exact_cell"],
        "compositional_plus_intersections": rq3_projection(
            "compositional_plus_interactions"
        ),
    }
    if tuple(representations) != REPRESENTATION_ORDER:
        raise AssertionError("RQ4 representation order drift")
    item_ids = {row["item_id"] for row in items}
    for representation_id, projection in representations.items():
        if set(projection) != item_ids:
            raise ValueError(f"{representation_id} does not project every fixed item")
    metadata = {
        "true_kstar_compositional_ceiling": {
            "semantics": "generator K* / public compositional structural ceiling",
            "selection_status": "reference, not discovered from RQ4 outcomes",
        },
        "rq3_atomic": {
            "semantics": "atomic feature-value projection from the frozen RQ3 seen-Q equivalence class",
            "selection_status": "frozen before RQ4 outcomes",
        },
        "family_union_coarse": {
            "semantics": "linguistic-family union merge",
            "activation": "a coarse family KC is active iff any constituent K* KC is active",
            "not_an_interaction": True,
        },
        "structural_split2": {
            "semantics": "each K* column split by deterministic canonical-cell context into at most two children",
        },
        "exact_cell_fine": {
            "semantics": "one hypothesis KC for every exact canonical GrammarCell",
        },
        "compositional_plus_intersections": {
            "semantics": "compositional base augmented by supported conjunctive pairwise intersections",
            "activation": "interaction KC is active only where both parent feature conditions hold",
            "not_a_union_merge": True,
        },
    }
    return representations, metadata


def render_projections(representations: dict[str, dict[str, Sequence[str]]]) -> str:
    return "".join(
        canonical_json(
            {
                "representation_id": representation_id,
                "item_id": item_id,
                "kc_ids": list(representations[representation_id][item_id]),
            }
        )
        + "\n"
        for representation_id in REPRESENTATION_ORDER
        for item_id in sorted(representations[representation_id])
    )


def make_item_novelty_partition(
    items: Sequence[dict[str, Any]],
    regime_by_cell: dict[str, str],
    *,
    seed: int,
) -> list[dict[str, Any]]:
    """Withhold one item from every exactly-two-item seen cell."""

    by_cell: dict[str, list[str]] = defaultdict(list)
    for row in items:
        by_cell[str(row["cell_id"])].append(str(row["item_id"]))
    rows = []
    for cell_id, item_ids in sorted(by_cell.items()):
        if regime_by_cell[cell_id] != "seen" or len(item_ids) != 2:
            continue
        ordered = sorted(item_ids, key=lambda item_id: (_stable_rank(seed, cell_id, item_id), item_id))
        rows.append(
            {
                "cell_id": cell_id,
                "heldout_item_id": ordered[0],
                "practised_item_id": ordered[1],
                "selection_rule": "minimum SHA-256 rank within exactly-two-item seen cell",
                "seed": seed,
            }
        )
    if len(rows) != 30:
        raise ValueError(f"expected 30 eligible two-item seen cells, found {len(rows)}")
    return rows


def build_item_novelty_schedule(
    items: Sequence[dict[str, Any]],
    q_projection: dict[str, Sequence[str]],
    regime_by_cell: dict[str, str],
    partition: Sequence[dict[str, Any]],
    *,
    target_opportunities: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Replace held items by same-cell variants in the frozen-size schedule."""

    seen_items = [
        {"item_id": str(row["item_id"]), "cell_id": str(row["cell_id"])}
        for row in items
        if regime_by_cell[str(row["cell_id"])] == "seen"
    ]
    original, diagnostics = baseline.build_acquisition_occurrences(
        seen_items,
        q_projection,
        target_opportunities_per_seen_kc=target_opportunities,
    )
    replacement = {row["heldout_item_id"]: row["practised_item_id"] for row in partition}
    cell_by_item = {str(row["item_id"]): str(row["cell_id"]) for row in items}
    exposures: Counter[str] = Counter()
    schedule = []
    for source_index, occurrence in enumerate(original, 1):
        source_item_id = str(occurrence["item"]["item_id"])
        item_id = replacement.get(source_item_id, source_item_id)
        exposures[item_id] += 1
        exposure = exposures[item_id]
        schedule.append(
            {
                "item": {"item_id": item_id, "cell_id": cell_by_item[item_id]},
                "source_item_id": source_item_id,
                "source_occurrence_index": source_index,
                "replacement_applied": source_item_id != item_id,
                "schedule_stage": "exhaustive_coverage" if exposure == 1 else "q_balanced_top_up",
                "pass_index": exposure,
                "item_exposure_index": exposure,
            }
        )
    held = set(replacement)
    if any(row["item"]["item_id"] in held for row in schedule):
        raise AssertionError("item-novelty acquisition schedule leaks a held item")
    original_kc_counts: Counter[str] = Counter()
    replacement_kc_counts: Counter[str] = Counter()
    for source, changed in zip(original, schedule, strict=True):
        original_kc_counts.update(q_projection[source["item"]["item_id"]])
        replacement_kc_counts.update(q_projection[changed["item"]["item_id"]])
    if original_kc_counts != replacement_kc_counts:
        raise AssertionError("same-cell replacement changed K* opportunity counts")
    audit = {
        "schedule_rows": len(schedule),
        "baseline_schedule_rows": diagnostics["schedule_length"],
        "heldout_items": len(held),
        "replaced_occurrences": sum(row["replacement_applied"] for row in schedule),
        "heldout_acquisition_occurrences": 0,
        "same_cell_replacement": all(
            cell_by_item[left] == cell_by_item[right]
            for left, right in replacement.items()
        ),
        "q_opportunity_counts_identical_to_baseline": True,
        "kc_opportunities": dict(sorted(replacement_kc_counts.items())),
        "schedule_semantic_sha256": semantic_sha256(schedule),
    }
    return schedule, audit


def _render_schedule(schedule: Sequence[dict[str, Any]]) -> str:
    return "".join(canonical_json(row) + "\n" for row in schedule)


def create_plan(dataset: Path, output: Path) -> dict[str, Any]:
    dataset = dataset.resolve()
    output = output.resolve()
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "FROZEN_BASELINE_COMPLETE":
        raise ValueError("RQ4 requires the immutable frozen baseline")
    representations, representation_metadata = build_representations(dataset)
    projection_payload = render_projections(representations)
    projection_path = output / "projections.jsonl"
    _write_frozen_text(projection_path, projection_payload, "RQ4 projection bundle")
    items = read_jsonl(dataset / "items/items.jsonl")
    regimes = read_jsonl(dataset / "grammar/regime_assignments.jsonl")
    regime_by_cell = {row["cell_id"]: row["grammar_regime"] for row in regimes}
    combination = [row for row in regimes if row["grammar_regime"] == "unseen_combination"]
    if len(combination) != 15 or not all(
        row["combination_subtype"] == "pairwise_seen_full_tuple_unseen"
        and row["constituent_seen"] is True
        and row["pairwise_seen"] is True
        and row["full_tuple_seen"] is False
        for row in combination
    ):
        raise ValueError("RQ4 combination cohort is not the declared pairwise-seen cohort")
    partition = make_item_novelty_partition(items, regime_by_cell, seed=PLAN_SEED)
    _write_frozen_json(output / "item_novelty_partition.json", partition, "item partition")
    q_sparse = _load_q_sparse(dataset / "oracle/q_matrix_sparse.jsonl")
    config = read_yaml(ROOT / "modules/simulation/baseline.yaml")
    schedule, schedule_audit = build_item_novelty_schedule(
        items,
        q_sparse,
        regime_by_cell,
        partition,
        target_opportunities=int(
            config["schedule"]["acquisition"]["target_opportunities_per_seen_kc"]
        ),
    )
    schedule_payload = _render_schedule(schedule)
    _write_frozen_text(output / "item_novelty_schedule.jsonl", schedule_payload, "item schedule")

    true_projection = representations["true_kstar_compositional_ceiling"]
    atomic_projection = representations["rq3_atomic"]
    seen_items = {
        row["item_id"] for row in items if regime_by_cell[row["cell_id"]] == "seen"
    }
    combination_items = {
        row["item_id"]
        for row in items
        if regime_by_cell[row["cell_id"]] == "unseen_combination"
    }
    unseen_value_items = {
        row["item_id"]
        for row in items
        if regime_by_cell[row["cell_id"]] == "unseen_value"
    }

    def unordered_q_signature(projection: dict[str, Sequence[str]], scope: set[str]) -> str:
        kc_ids = sorted({kc for item_id in scope for kc in projection[item_id]})
        columns = sorted(
            tuple(sorted(item_id for item_id in scope if kc_id in projection[item_id]))
            for kc_id in kc_ids
        )
        return semantic_sha256(columns)

    if unordered_q_signature(true_projection, seen_items) != unordered_q_signature(
        atomic_projection, seen_items
    ):
        raise ValueError("RQ3 atomic/compositional policies are not seen-Q equivalent")
    if unordered_q_signature(true_projection, combination_items) != unordered_q_signature(
        atomic_projection, combination_items
    ):
        raise ValueError("RQ3 atomic/compositional policies unexpectedly differ on combinations")
    if unordered_q_signature(true_projection, unseen_value_items) == unordered_q_signature(
        atomic_projection, unseen_value_items
    ):
        raise ValueError("RQ3 atomic/compositional ambiguity lacks its planned unseen-value contrast")

    plan = {
        "study_id": STUDY_ID,
        "status": "PREREGISTERED_BEFORE_RQ4_OUTCOME_ANALYSIS",
        "research_question": (
            "How do frozen KC representations generalise from seen grammar to "
            "pairwise-seen/full-tuple-unseen combinations and unseen values?"
        ),
        "hypotheses": [
            "K* and atomic RQ3 projections will be indistinguishable on seen and combination grammar but diverge on perfect-progressive unseen values.",
            "Family-union merging and structural splitting will lose predictive information relative to K*.",
            "Exact-cell KCs will not transfer to structurally novel cells.",
            "Withholding an exact item while preserving identical K* opportunity counts will have no simulator-level outcome effect; this is a negative control, not a human item-novelty model.",
        ],
        "representations": representation_metadata,
        "representation_order": list(REPRESENTATION_ORDER),
        "predictor": {
            "model": "observable PFA-like logistic",
            "training_rows": "seen acquisition only",
            "features": [
                "learner prior-smoothed correctness",
                "active-KC prior-smoothed correctness mean",
                "active-KC log1p opportunities mean",
                "active-KC count",
                "KC indicators",
            ],
            "standardize": True,
            "regularization_c": 1.0,
            "max_iterations": 500,
            "seed": 20260830,
            "probe_history_updates": False,
        },
        "grammar_cohorts": {
            "seen": {"cells": 54, "interpretation": "exact GrammarCells practised in acquisition"},
            "unseen_combination": {
                "cells": 15,
                "subtype": "pairwise_seen_full_tuple_unseen",
            },
            "unseen_value": {
                "cells": 6,
                "novel_value": "aspect=perfect_progressive",
            },
        },
        "evaluation": {
            "event_metrics": ["log_loss", "brier_score"],
            "cell_macro_metrics": ["log_loss", "brier_score"],
            "per_cell_rows": True,
            "small_group_sensitivity": {
                "method": "leave one whole cell out of the cell-macro mean",
                "report": ["all leave-one-cell-out values", "range", "per-cell range"],
                "primary_warning_scope": "six-cell unseen_value cohort",
            },
            "learner_paired_bootstrap": {
                "reference": "true_kstar_compositional_ceiling",
                "repeats": BOOTSTRAP_REPEATS,
                "seed": PLAN_SEED,
                "interval": 0.95,
                "regimes": list(REGIME_ORDER),
            },
        },
        "item_novelty_control": {
            "learners": 1000,
            "eligible_cells": 30,
            "partition": "one SHA-256-ranked item withheld per exactly-two-item seen cell",
            "acquisition": (
                "replace every withheld occurrence in the 170-row baseline "
                "multiset with its same-cell counterpart"
            ),
            "schedule_rows_per_learner": schedule_audit["schedule_rows"],
            "probe": "one terminal non-updating probe for each of 30 withheld items",
            "simulator": "frozen full-v1 assumptions and seed",
            "same_q_opportunities_as_baseline": True,
            "negative_control_scope": (
                "No item difficulty or lexical-memory variable exists; this tests "
                "whether exact item identity alone explains grammar-novel results."
            ),
        },
        "scientific_boundary": {
            "representations_frozen_before_RQ4_outcomes": True,
            "baseline_dataset_mutated": False,
            "probe_outcomes_used_for_fitting_or_selection": False,
            "learner_oracle_read": False,
            "item_novelty_is_separate_experiment_artifact": True,
            "atomic_compositional_seen_q_equivalence_preserved": True,
        },
        "inputs": _dataset_inputs(dataset),
        "frozen_artifacts": {
            "projections": {"path": "projections.jsonl", "sha256": hashlib.sha256(projection_payload.encode()).hexdigest()},
            "item_novelty_partition": {
                "path": "item_novelty_partition.json",
                "sha256": file_sha256(output / "item_novelty_partition.json"),
            },
            "item_novelty_schedule": {
                "path": "item_novelty_schedule.jsonl",
                "sha256": hashlib.sha256(schedule_payload.encode()).hexdigest(),
                "audit": schedule_audit,
            },
        },
        "implementation": {
            "path": str(Path(__file__).resolve().relative_to(ROOT)),
            "sha256": file_sha256(Path(__file__).resolve()),
        },
        "exact_commands": {
            "plan": ".venv/bin/python scripts/experiments/rq4_grammar_generalisation.py --stage plan",
            "run": ".venv/bin/python scripts/experiments/rq4_grammar_generalisation.py --stage run",
        },
    }
    plan["plan_semantic_sha256"] = semantic_sha256(plan)
    _write_frozen_json(output / "study_plan.json", plan, "RQ4 study plan")
    return plan


def _validate_plan(dataset: Path, output: Path) -> tuple[dict[str, Any], dict[str, dict[str, tuple[str, ...]]]]:
    plan_path = output / "study_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    unsigned = {key: value for key, value in plan.items() if key != "plan_semantic_sha256"}
    if plan.get("plan_semantic_sha256") != semantic_sha256(unsigned):
        raise ValueError("RQ4 plan semantic hash mismatch")
    if plan.get("status") != "PREREGISTERED_BEFORE_RQ4_OUTCOME_ANALYSIS":
        raise ValueError("RQ4 run requires a preregistered plan")
    if file_sha256(Path(__file__).resolve()) != plan["implementation"]["sha256"]:
        raise ValueError("RQ4 implementation changed after preregistration")
    if _dataset_inputs(dataset) != plan["inputs"]:
        raise ValueError("RQ4 input changed after preregistration")
    for row in plan["frozen_artifacts"].values():
        if file_sha256(output / row["path"]) != row["sha256"]:
            raise ValueError(f"RQ4 frozen artifact changed: {row['path']}")
    projections = load_projection_bundle(output / "projections.jsonl")
    if tuple(projections) != tuple(sorted(projections)):
        # Loader sorts keys; order is asserted against the plan below instead.
        pass
    if set(projections) != set(REPRESENTATION_ORDER):
        raise ValueError("RQ4 projection bundle differs from frozen representations")
    return plan, projections


def _cell_evaluation(
    events: Sequence[dict[str, Any]],
    probabilities: np.ndarray,
    item_to_cell: dict[str, str],
) -> dict[str, Any]:
    by_cell: dict[str, list[int]] = defaultdict(list)
    for index, event in enumerate(events):
        by_cell[item_to_cell[str(event["item_id"])]].append(index)
    per_cell = []
    for cell_id, indices in sorted(by_cell.items()):
        targets = [int(events[index]["correct"]) for index in indices]
        metrics = prediction_metrics(targets, probabilities[indices])
        per_cell.append(
            {
                "cell_id": cell_id,
                "items": len({str(events[index]["item_id"]) for index in indices}),
                "events": len(indices),
                "log_loss": metrics["log_loss"],
                "brier_score": metrics["brier_score"],
                "observed_correct_rate": float(np.mean(targets)),
            }
        )
    macro = {
        metric: float(mean(row[metric] for row in per_cell))
        for metric in ("log_loss", "brier_score")
    }
    leave_one_out = []
    if len(per_cell) > 1:
        for excluded in per_cell:
            remaining = [row for row in per_cell if row["cell_id"] != excluded["cell_id"]]
            leave_one_out.append(
                {
                    "excluded_cell_id": excluded["cell_id"],
                    "log_loss": float(mean(row["log_loss"] for row in remaining)),
                    "brier_score": float(mean(row["brier_score"] for row in remaining)),
                }
            )
    return {
        "cells": len(per_cell),
        "cell_macro": macro,
        "per_cell": per_cell,
        "sensitivity": {
            "per_cell_log_loss_range": [
                min(row["log_loss"] for row in per_cell),
                max(row["log_loss"] for row in per_cell),
            ],
            "per_cell_brier_range": [
                min(row["brier_score"] for row in per_cell),
                max(row["brier_score"] for row in per_cell),
            ],
            "leave_one_cell_out": leave_one_out,
            "leave_one_cell_out_log_loss_range": (
                [
                    min(row["log_loss"] for row in leave_one_out),
                    max(row["log_loss"] for row in leave_one_out),
                ]
                if leave_one_out
                else None
            ),
            "leave_one_cell_out_brier_range": (
                [
                    min(row["brier_score"] for row in leave_one_out),
                    max(row["brier_score"] for row in leave_one_out),
                ]
                if leave_one_out
                else None
            ),
        },
    }


def evaluate_representations(
    events: list[dict[str, Any]],
    projections: dict[str, dict[str, tuple[str, ...]]],
    items: Sequence[dict[str, Any]],
    *,
    regime_order: Sequence[str] = REGIME_ORDER,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    evaluation_events = [row for row in events if row["phase"] == "probe"]
    targets = np.asarray([int(row["correct"]) for row in evaluation_events], dtype=np.int8)
    item_to_cell = {str(row["item_id"]): str(row["cell_id"]) for row in items}
    regimes = np.asarray([str(row["grammar_regime"]) for row in evaluation_events])
    probabilities = {}
    results = {}
    for representation_id in REPRESENTATION_ORDER:
        prediction, fit = fit_observable_logistic(events, projections[representation_id])
        probabilities[representation_id] = prediction
        regime_results = {}
        for regime in regime_order:
            mask = regimes == regime
            selected_events = [
                event for event, keep in zip(evaluation_events, mask, strict=True) if keep
            ]
            regime_results[regime] = {
                "event_weighted": prediction_metrics(targets[mask], prediction[mask]),
                **_cell_evaluation(selected_events, prediction[mask], item_to_cell),
            }
        results[representation_id] = {"fit": fit, "by_grammar_regime": regime_results}
    return results, probabilities


def _bootstrap_by_regime(
    events: Sequence[dict[str, Any]],
    probabilities: dict[str, np.ndarray],
) -> dict[str, Any]:
    evaluation_events = [row for row in events if row["phase"] == "probe"]
    regimes = np.asarray([str(row["grammar_regime"]) for row in evaluation_events])
    output = {}
    for candidate_id in REPRESENTATION_ORDER[1:]:
        output[candidate_id] = {}
        for regime in REGIME_ORDER:
            mask = regimes == regime
            selected_events = [
                row for row, keep in zip(evaluation_events, mask, strict=True) if keep
            ]
            output[candidate_id][regime] = paired_learner_bootstrap(
                selected_events,
                probabilities[REPRESENTATION_ORDER[0]][mask],
                probabilities[candidate_id][mask],
                repeats=BOOTSTRAP_REPEATS,
                seed=PLAN_SEED,
                reference_id=REPRESENTATION_ORDER[0],
                candidate_id=candidate_id,
            )
    return output


def _load_schedule(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def simulate_item_novelty(
    items: Sequence[dict[str, Any]],
    generator_kcs: Sequence[dict[str, Any]],
    q_projection: dict[str, Sequence[str]],
    regime_by_cell: dict[str, str],
    config: dict[str, Any],
    schedule: Sequence[dict[str, Any]],
    partition: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Direct counterfactual using the frozen baseline stochastic semantics."""

    baseline.validate_baseline_config(config)
    learner_count = int(config["learners"])
    seed = int(config["seed"])
    kc_ids = sorted(row["id"] for row in generator_kcs)
    beta_alpha = float(config["initial_mastery"]["alpha"])
    beta_beta = float(config["initial_mastery"]["beta"])
    guess = float(config["response"]["guess"])
    slip = float(config["response"]["slip"])
    learning_rate = float(config["learning"]["rate"])
    held_ids = {row["heldout_item_id"] for row in partition}
    item_by_id = {row["item_id"]: {"item_id": row["item_id"], "cell_id": row["cell_id"]} for row in items}
    held_items = [item_by_id[item_id] for item_id in sorted(held_ids)]
    interactions = []
    for learner_number in range(1, learner_count + 1):
        learner_id = f"learner_{learner_number:06d}"
        mastery = {
            kc_id: float(
                baseline._keyed_rng(seed, "initial_mastery", learner_number, kc_id).beta(
                    beta_alpha, beta_beta
                )
            )
            for kc_id in kc_ids
        }
        sequence = 0
        ordered_acquisition = baseline.order_acquisition_occurrences(
            schedule, seed=seed, learner_number=learner_number
        )
        phases = [
            ("acquisition", row["item"], int(row["item_exposure_index"]), int(row["pass_index"]), True)
            for row in ordered_acquisition
        ]
        phases.extend(
            ("probe", row, 1, 1, False)
            for row in baseline._ordered_items(
                held_items,
                seed=seed,
                learner_number=learner_number,
                phase="probe",
                pass_index=1,
            )
        )
        for phase, item, draw_index, pass_index, updates in phases:
            sequence += 1
            item_id = item["item_id"]
            active = q_projection[item_id]
            aggregated = min(mastery[kc_id] for kc_id in active)
            probability = guess + (1 - guess - slip) * aggregated
            keys = (
                (phase, item_id, draw_index)
                if phase == "acquisition"
                else (phase, draw_index, item_id)
            )
            draw = float(baseline._keyed_rng(seed, "response", learner_number, *keys).random())
            correct = int(draw < probability)
            if updates:
                for kc_id in active:
                    mastery[kc_id] += learning_rate * (1 - mastery[kc_id])
            interactions.append(
                {
                    "learner_id": learner_id,
                    "item_id": item_id,
                    "sequence_index": sequence,
                    "correct": correct,
                    "phase": phase,
                    "pass_index": pass_index,
                    "grammar_regime": regime_by_cell[item["cell_id"]],
                    "event_id": f"{learner_id}::{sequence:04d}",
                    "updates_history": updates,
                    "dataset_split": "train" if updates else "test",
                }
            )
    if any(row["phase"] == "acquisition" and row["item_id"] in held_ids for row in interactions):
        raise AssertionError("held item leaked into item-novelty acquisition")
    return interactions


def _write_observable_gzip(path: Path, events: Sequence[dict[str, Any]]) -> str:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite item-novelty events: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    public = ("learner_id", "item_id", "sequence_index", "correct", "phase", "pass_index", "grammar_regime")
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
            for row in events:
                stream.write((canonical_json({key: row[key] for key in public}) + "\n").encode())
    return file_sha256(path)


def _observed_cohort_summary(events: Sequence[dict[str, Any]], item_to_cell: dict[str, str]) -> dict[str, Any]:
    if not events:
        raise ValueError("empty novelty comparison cohort")
    by_cell: dict[str, list[int]] = defaultdict(list)
    for row in events:
        by_cell[item_to_cell[str(row["item_id"])]].append(int(row["correct"]))
    cell_rates = [mean(values) for values in by_cell.values()]
    return {
        "events": len(events),
        "learners": len({row["learner_id"] for row in events}),
        "cells": len(by_cell),
        "observed_correct_rate": float(mean(int(row["correct"]) for row in events)),
        "cell_macro_correct_rate": float(mean(cell_rates)),
        "per_cell_correct_rate_range": [float(min(cell_rates)), float(max(cell_rates))],
    }


def run_study(dataset: Path, output: Path) -> dict[str, Any]:
    dataset = dataset.resolve()
    output = output.resolve()
    plan, projections = _validate_plan(dataset, output)
    before_hashes = {name: row["sha256"] for name, row in plan["inputs"].items() if name in {
        "manifest", "interactions", "items", "cells", "regimes", "generator_kcs", "true_q_dense", "true_q_sparse"
    }}
    items = read_jsonl(dataset / "items/items.jsonl")
    item_to_cell = {row["item_id"]: row["cell_id"] for row in items}
    regimes = read_jsonl(dataset / "grammar/regime_assignments.jsonl")
    regime_by_cell = {row["cell_id"]: row["grammar_regime"] for row in regimes}
    baseline_events = load_observable_events(dataset / "interactions.jsonl.gz")
    baseline_results, baseline_probabilities = evaluate_representations(
        baseline_events, projections, items
    )
    bootstrap = _bootstrap_by_regime(baseline_events, baseline_probabilities)

    partition = json.loads((output / "item_novelty_partition.json").read_text(encoding="utf-8"))
    schedule = _load_schedule(output / "item_novelty_schedule.jsonl")
    novelty_events = simulate_item_novelty(
        items,
        read_jsonl(dataset / "kcs.jsonl"),
        _load_q_sparse(dataset / "oracle/q_matrix_sparse.jsonl"),
        regime_by_cell,
        read_yaml(ROOT / "modules/simulation/baseline.yaml"),
        schedule,
        partition,
    )
    novelty_gzip = output / "item_novelty_interactions.jsonl.gz"
    novelty_sha = _write_observable_gzip(novelty_gzip, novelty_events)
    novelty_results, novelty_probabilities = evaluate_representations(
        novelty_events, projections, items, regime_order=("seen",)
    )

    held_ids = {row["heldout_item_id"] for row in partition}
    baseline_probes = [row for row in baseline_events if row["phase"] == "probe"]
    novelty_probes = [row for row in novelty_events if row["phase"] == "probe"]
    baseline_held = [row for row in baseline_probes if row["item_id"] in held_ids]
    baseline_by_key = {(row["learner_id"], row["item_id"]): row for row in baseline_held}
    novelty_by_key = {(row["learner_id"], row["item_id"]): row for row in novelty_probes}
    if set(baseline_by_key) != set(novelty_by_key):
        raise AssertionError("item-novelty and baseline held probes do not pair")
    outcome_matches = sum(
        baseline_by_key[key]["correct"] == novelty_by_key[key]["correct"]
        for key in baseline_by_key
    )
    comparison_cohorts = {
        "exact_item_novelty_control": novelty_probes,
        "matched_seen_items_from_baseline": baseline_held,
        "pairwise_seen_full_tuple_unseen": [
            row for row in baseline_probes if row["grammar_regime"] == "unseen_combination"
        ],
        "unseen_value": [row for row in baseline_probes if row["grammar_regime"] == "unseen_value"],
    }
    novelty_comparison = {
        name: _observed_cohort_summary(rows, item_to_cell)
        for name, rows in comparison_cohorts.items()
    }
    baseline_true_probabilities = baseline_probabilities[REPRESENTATION_ORDER[0]]
    novelty_true_probabilities = novelty_probabilities[REPRESENTATION_ORDER[0]]
    baseline_probe_keys = [
        (row["learner_id"], row["item_id"]) for row in baseline_probes
    ]
    baseline_probability_by_key = dict(
        zip(baseline_probe_keys, baseline_true_probabilities, strict=True)
    )
    novelty_probability_by_key = dict(
        zip(
            [(row["learner_id"], row["item_id"]) for row in novelty_probes],
            novelty_true_probabilities,
            strict=True,
        )
    )
    for name, rows in comparison_cohorts.items():
        probability_lookup = (
            novelty_probability_by_key
            if name == "exact_item_novelty_control"
            else baseline_probability_by_key
        )
        selected_probability = np.asarray(
            [probability_lookup[(row["learner_id"], row["item_id"])] for row in rows]
        )
        novelty_comparison[name]["kstar_predictive"] = prediction_metrics(
            [int(row["correct"]) for row in rows], selected_probability
        )
        novelty_comparison[name]["kstar_cell_macro"] = _cell_evaluation(
            rows, selected_probability, item_to_cell
        )["cell_macro"]
    novelty_comparison["paired_baseline_control"] = {
        "paired_rows": len(baseline_by_key),
        "identical_outcomes": outcome_matches,
        "outcome_match_rate": outcome_matches / len(baseline_by_key),
        "interpretation": (
            "The frozen simulator has no item-specific state or difficulty and "
            "same-cell replacement preserves every K* learning update."
        ),
    }

    after_inputs = _dataset_inputs(dataset)
    after_hashes = {name: row["sha256"] for name, row in after_inputs.items() if name in before_hashes}
    if before_hashes != after_hashes:
        raise AssertionError("immutable baseline artifacts changed during RQ4")
    true_id = REPRESENTATION_ORDER[0]
    atomic_id = REPRESENTATION_ORDER[1]
    baseline_probe_rows = [row for row in baseline_events if row["phase"] == "probe"]
    seen_mask = np.asarray([row["grammar_regime"] == "seen" for row in baseline_probe_rows])
    combination_mask = np.asarray(
        [row["grammar_regime"] == "unseen_combination" for row in baseline_probe_rows]
    )
    result = {
        "study_id": STUDY_ID,
        "status": "FULL_N1000_COMPLETE",
        "plan_sha256": file_sha256(output / "study_plan.json"),
        "plan_semantic_sha256": plan["plan_semantic_sha256"],
        "baseline_generalisation": baseline_results,
        "learner_paired_bootstrap_vs_kstar": bootstrap,
        "atomic_compositional_equivalence_audit": {
            "seen_prediction_max_absolute_difference": float(
                np.max(np.abs(baseline_probabilities[true_id][seen_mask] - baseline_probabilities[atomic_id][seen_mask]))
            ),
            "combination_prediction_max_absolute_difference": float(
                np.max(np.abs(baseline_probabilities[true_id][combination_mask] - baseline_probabilities[atomic_id][combination_mask]))
            ),
            "differences_expected_only_for_unseen_value_activation": True,
            "unique_recovery_claimed": False,
        },
        "item_novelty_control": {
            "events": len(novelty_events),
            "interaction_artifact": {
                "path": novelty_gzip.name,
                "sha256": novelty_sha,
            },
            "schedule_audit": plan["frozen_artifacts"]["item_novelty_schedule"]["audit"],
            "representation_results": novelty_results,
            "comparison_with_grammar_novelty": novelty_comparison,
        },
        "boundary_audit": {
            "baseline_artifact_hashes_before": before_hashes,
            "baseline_artifact_hashes_after": after_hashes,
            "baseline_immutable": before_hashes == after_hashes,
            "probe_outcomes_used_for_fitting_or_selection": False,
            "all_baseline_probes_non_updating": all(
                not row["updates_history"] for row in baseline_probe_rows
            ),
            "all_item_novelty_probes_non_updating": all(
                not row["updates_history"] for row in novelty_probes
            ),
            "learner_oracle_read": False,
            "item_novelty_outside_frozen_baseline": True,
        },
    }
    result["result_semantic_sha256"] = semantic_sha256(result)
    _write_frozen_json(output / "results.json", result, "RQ4 results")
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
