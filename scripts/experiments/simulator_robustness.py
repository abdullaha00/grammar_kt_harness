#!/usr/bin/env python3
"""Plan and run compact downstream simulator robustness over frozen full-v1.

The plan stage freezes the one-factor sensitivity worlds and three outcome-free
KC representations before any responses are generated.  The run stage creates
one observable event stream per world/seed and supplies that identical stream
to every representation's observable-history logistic predictor.  Neither the
frozen interaction file nor any private learner-oracle file is read.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Mapping, Sequence

import numpy as np
import sklearn

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grammar_kt.baseline_simulation import OBSERVABLE_FIELDS
from grammar_kt.io import read_yaml
from grammar_kt.sensitivity_simulation import (
    SensitivityCondition,
    simulate_sensitivity,
)
from scripts.experiments.rq2_kc_misspecification import (
    coarse_projection,
    fit_observable_logistic,
    load_true_projection,
    prediction_metrics,
    structural_split_projection,
    validate_projection,
)


DEFAULT_DATASET = ROOT / "data/grammar_kt_full_v1"
DEFAULT_OUTPUT = ROOT / "experiments/full_v1/simulator_robustness_v1"
STUDY_ID = "full_v1_compact_simulator_robustness_v1"
LEARNERS = 500
SEEDS = (20260829, 20260830, 20260831)
MODEL_SEED = 20260830
REPRESENTATION_ORDER = (
    "true_kstar",
    "coarse_linguistic_families",
    "structural_split2",
)
REFERENCE_REPRESENTATION = "true_kstar"
METRIC_NAMES = ("log_loss", "brier_score")
PRIMARY_MODEL = "observable_pfa_logistic_primary"
EMPIRICAL_MODEL = "empirical_history_secondary"
BKT_MODEL = "bkt_mean_full_credit_secondary"
MODEL_ORDER = (PRIMARY_MODEL, EMPIRICAL_MODEL, BKT_MODEL)
EMPIRICAL_ALPHA = 1.0
EMPIRICAL_BETA = 1.0
BKT_PARAMETERS = {
    "initial_mastery": 0.35,
    "learn": 0.12,
    "guess": 0.18,
    "slip": 0.10,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _repository_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _write_frozen_text(path: Path, payload: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def _write_frozen_json(path: Path, value: Any, label: str) -> None:
    _write_frozen_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        label,
    )


def planned_conditions() -> list[dict[str, Any]]:
    """Return the complete frozen one-factor sensitivity design."""

    definitions = [
        (
            SensitivityCondition("baseline_minimum_g10_s10"),
            "Frozen baseline dynamics; reference for rank and sign reversals.",
        ),
        (
            SensitivityCondition(
                "noise_g00_s00",
                guess=0.0,
                slip=0.0,
            ),
            "Noise-free boundary separates ontology effects from irreducible response noise.",
        ),
        (
            SensitivityCondition(
                "noise_g20_s10",
                guess=0.20,
                slip=0.10,
            ),
            "Raise guess alone to distinguish lower-tail noise from slip.",
        ),
        (
            SensitivityCondition(
                "noise_g10_s20",
                guess=0.10,
                slip=0.20,
            ),
            "Raise slip alone to distinguish upper-tail noise from guess.",
        ),
        (
            SensitivityCondition(
                "noise_g20_s20",
                guess=0.20,
                slip=0.20,
            ),
            "Raise both response-noise bounds without adding a larger noise grid.",
        ),
        (
            SensitivityCondition(
                "aggregation_product",
                aggregation="product",
            ),
            "Non-compensatory product is the strongest concise alternative to minimum.",
        ),
        (
            SensitivityCondition(
                "aggregation_arithmetic_mean",
                aggregation="arithmetic_mean",
            ),
            "Arithmetic mean is the canonical compensatory contrast to minimum.",
        ),
        (
            SensitivityCondition(
                "learner_guess_slip_heterogeneity_beta2_2_00_20",
                learner_guess_slip_range=(0.0, 0.20),
            ),
            "One bounded learner-noise distribution preserves mean 0.10 while testing heterogeneity.",
        ),
        (
            SensitivityCondition(
                "forgetting_gap_002",
                forgetting_per_acquisition_gap=0.002,
            ),
            "A single mild per-gap decay accumulates over the fixed acquisition schedule.",
        ),
        (
            SensitivityCondition(
                "item_difficulty_logit_sd_060",
                item_difficulty_logit_sd=0.60,
            ),
            "One centered item logit-offset distribution tests unmodelled item variation.",
        ),
        (
            SensitivityCondition(
                "learner_learning_rate_heterogeneity_beta2_2_005_035",
                learner_learning_rate_range=(0.005, 0.035),
            ),
            "One bounded learner-rate distribution preserves mean 0.02 while testing heterogeneity.",
        ),
        (
            SensitivityCondition(
                "correlated_initial_mastery_global_mixture_050",
                initial_mastery_global_mixture_weight=0.50,
            ),
            "A 0.50 learner-global/independent Beta(2,2) selection mixture induces initial-mastery correlation while preserving every KC marginal; it is not directed prerequisite learning.",
        ),
        (
            SensitivityCondition(
                "update_correct_only",
                update_rule="correct_only",
            ),
            "Correct-only updating is one transparent correctness-dependent boundary case.",
        ),
    ]
    return [
        {"condition": condition.to_dict(), "rationale": rationale}
        for condition, rationale in definitions
    ]


def _plan_input_paths(dataset_dir: Path) -> dict[str, Path]:
    return {
        "manifest": dataset_dir / "manifest.json",
        "items": dataset_dir / "items/items.jsonl",
        "cells": dataset_dir / "grammar/cells.jsonl",
        "generator_kcs": dataset_dir / "kcs.jsonl",
        "true_q_matrix": dataset_dir / "q_matrix.csv",
        "grammar_regimes": dataset_dir / "grammar/regime_assignments.jsonl",
        "baseline_design": dataset_dir / "provenance/simulation/baseline.yaml",
    }


def _plan_inputs(dataset_dir: Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for name, path in _plan_input_paths(dataset_dir).items():
        if not path.is_file():
            raise FileNotFoundError(path)
        output[name] = {
            "path": str(path.relative_to(dataset_dir)),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
    return output


def _load_fixed_inputs(dataset_dir: Path) -> dict[str, Any]:
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "FROZEN_BASELINE_COMPLETE":
        raise ValueError("simulator robustness requires a frozen full-v1 baseline")
    expected_scale = {
        "canonical_grammar_cells": 75,
        "generator_kcs": 18,
        "items": 113,
        "q_edges": 269,
    }
    for key, expected in expected_scale.items():
        if int(manifest["scale"][key]) != expected:
            raise ValueError(f"frozen full-v1 scale changed for {key}")
    items = _read_jsonl(dataset_dir / "items/items.jsonl")
    cells = _read_jsonl(dataset_dir / "grammar/cells.jsonl")
    kcs = _read_jsonl(dataset_dir / "kcs.jsonl")
    regime_rows = _read_jsonl(dataset_dir / "grammar/regime_assignments.jsonl")
    regime_by_cell = {
        str(row["cell_id"]): str(row["grammar_regime"]) for row in regime_rows
    }
    if len(regime_by_cell) != len(regime_rows):
        raise ValueError("grammar regimes contain duplicate cells")
    true_kc_ids, true_projection = load_true_projection(dataset_dir / "q_matrix.csv")
    declared_kcs = sorted(str(row["id"]) for row in kcs)
    if sorted(true_kc_ids) != declared_kcs:
        raise ValueError("generator K* and Q* columns disagree")
    if len(items) != 113 or len(cells) != 75 or len(declared_kcs) != 18:
        raise ValueError("fixed artifact row counts disagree with frozen scale")
    if sum(len(active) for active in true_projection.values()) != 269:
        raise ValueError("true Q* edge count differs from frozen scale")
    design_config = read_yaml(dataset_dir / "provenance/simulation/baseline.yaml")
    return {
        "manifest": manifest,
        "items": items,
        "cells": cells,
        "generator_kc_ids": declared_kcs,
        "true_projection": true_projection,
        "regime_by_cell": regime_by_cell,
        "design_config": design_config,
    }


def _build_representations(fixed: Mapping[str, Any]) -> dict[str, dict[str, tuple[str, ...]]]:
    truth = {
        item_id: tuple(active)
        for item_id, active in fixed["true_projection"].items()
    }
    representations = {
        "true_kstar": truth,
        "coarse_linguistic_families": coarse_projection(
            truth, fixed["generator_kc_ids"]
        ),
        "structural_split2": structural_split_projection(
            truth,
            fixed["items"],
            fixed["cells"],
            2,
        ),
    }
    for representation_id in REPRESENTATION_ORDER:
        validate_projection(representations[representation_id], truth)
    return representations


def _render_projection_bundle(
    representations: Mapping[str, Mapping[str, Sequence[str]]],
) -> str:
    return "".join(
        _canonical_json(
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


def _load_projection_bundle(path: Path) -> dict[str, dict[str, tuple[str, ...]]]:
    output: dict[str, dict[str, tuple[str, ...]]] = defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        representation_id = str(row["representation_id"])
        item_id = str(row["item_id"])
        if item_id in output[representation_id]:
            raise ValueError("projection bundle duplicates representation/item")
        output[representation_id][item_id] = tuple(str(kc) for kc in row["kc_ids"])
    if tuple(output) != REPRESENTATION_ORDER:
        raise ValueError("projection bundle representation order changed")
    return {key: dict(value) for key, value in output.items()}


def _implementation_hashes() -> dict[str, str]:
    paths = [
        Path(__file__).resolve(),
        ROOT / "src/grammar_kt/sensitivity_simulation.py",
        ROOT / "src/grammar_kt/baseline_simulation.py",
        ROOT / "scripts/experiments/rq2_kc_misspecification.py",
    ]
    return {
        str(path.relative_to(ROOT)): file_sha256(path)
        for path in paths
    }


def create_plan(dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    fixed = _load_fixed_inputs(dataset_dir)
    representations = _build_representations(fixed)
    projection_payload = _render_projection_bundle(representations)
    projection_path = output_dir / "projections.jsonl"
    _write_frozen_text(
        projection_path,
        projection_payload,
        "preregistered projection bundle",
    )
    representation_audits = {
        representation_id: validate_projection(
            representations[representation_id], fixed["true_projection"]
        )
        for representation_id in REPRESENTATION_ORDER
    }
    plan = {
        "study_id": STUDY_ID,
        "status": "PLANNED_BEFORE_RESPONSE_GENERATION",
        "question": "Does KC-representation ranking under one observable logistic survive compact perturbations of declared simulator assumptions?",
        "fixed_measurement_scope": {
            "grammar_cells": 75,
            "items": 113,
            "generator_kcs": 18,
            "q_edges": 269,
            "item_bank_changed": False,
            "q_star_changed": False,
        },
        "execution_design": {
            "learners_per_world": LEARNERS,
            "seeds": list(SEEDS),
            "conditions": planned_conditions(),
            "representations": list(REPRESENTATION_ORDER),
            "worlds": len(SEEDS) * len(planned_conditions()),
            "primary_logistic_fits": len(SEEDS)
            * len(planned_conditions())
            * len(REPRESENTATION_ORDER),
            "secondary_model_evaluations": len(SEEDS)
            * len(planned_conditions())
            * len(REPRESENTATION_ORDER)
            * 2,
            "acquisition_item_ids": None,
            "novelty_grid_executed": False,
        },
        "frozen_reduction_rationale": [
            "Use the requested 500 learners and three common seeds; do not add a sample-size grid.",
            "Vary one simulator assumption at a time around the baseline, except the four explicitly requested guess/slip pairs.",
            "Use one bounded distribution each for learner noise, item difficulty, and learner learning rate rather than severity grids.",
            "Use one exact marginal-preserving correlated-initial-mastery mixture; do not add a prerequisite or correlation-strength grid.",
            "Use one mild forgetting rate and one transparent correct-only update boundary rather than factorial combinations.",
            "Evaluate K*, coarse linguistic families, and structural split2 only, with the same fixed observable logistic and all terminal probes.",
            "Retain seed-wise deltas and reversal diagnostics; do not add bootstrap, novelty, KT-model, or regime grids.",
            "Materialize worlds transiently and persist aggregate results/hashes only, avoiding redundant event copies across representations.",
        ],
        "common_random_numbers": {
            "scheme": "keyed_sha256_v1",
            "shared_across_conditions_within_seed": [
                "initial K* mastery beta draws",
                "response uniform draws keyed by learner/phase/item/exposure",
                "learner heterogeneity Beta(2,2) latent draws",
                "item difficulty standard-normal latent draws",
                "learner-keyed acquisition and probe order ranks",
            ],
            "verification": "Every condition within a seed must have identical common-random-number hashes and event keys.",
        },
        "sensitivity_semantics": {
            "response": "guess + (1 - guess - slip) * logistic(logit(aggregate mastery) - item difficulty)",
            "heterogeneity_distribution": "independent Beta(2,2) quantiles scaled to each declared bounded interval",
            "forgetting": "before every acquisition response after the first, decay every K* mastery by the declared per-gap rate; no additional pre-probe gap",
            "correctness_dependent_update": "correct-only active-KC learning update",
            "correlated_initial_mastery": "for each learner, draw global G and learner-KC independent I from Beta(2,2); a keyed Bernoulli with declared mixture weight selects G versus I, preserving the Beta(2,2) KC marginal while inducing undirected correlation",
            "prerequisite_learning_modelled": False,
            "probes": "terminal complete-bank snapshot; non-updating",
        },
        "outcome_free_acquisition_hook": {
            "parameter": "acquisition_item_ids",
            "availability": "implemented and tested",
            "constraint": "fixed item IDs in the declared acquisition grammar regime only",
            "used_in_this_run": False,
            "purpose": "later RQ4 acquisition-set control without consulting outcomes",
        },
        "predictors": {
            "primary": {
                "model_id": PRIMARY_MODEL,
                "name": "observable_history_logistic_pfa_like",
                "implementation": "fit_observable_logistic from scripts/experiments/rq2_kc_misspecification.py",
                "training_rows": "all acquisition events",
                "evaluation_rows": "all terminal probe events",
                "features": [
                    "prior-smoothed learner correctness",
                    "mean prior-smoothed active-hypothesis-KC correctness",
                    "mean log1p active-hypothesis-KC opportunities",
                    "active hypothesis-KC count",
                    "hypothesis-KC indicators",
                ],
                "history_update_flag": "deterministically derived as phase == acquisition from the observable phase field",
                "standardize": True,
                "regularization_c": 1.0,
                "max_iterations": 500,
                "random_seed": MODEL_SEED,
            },
            "secondary": [
                {
                    "model_id": EMPIRICAL_MODEL,
                    "name": "prior-smoothed active-KC empirical history",
                    "alpha": EMPIRICAL_ALPHA,
                    "beta": EMPIRICAL_BETA,
                    "role": "transparent nonparametric history sensitivity only",
                },
                {
                    "model_id": BKT_MODEL,
                    "name": "simple per-KC BKT with mean multi-KC response and full-credit outcome update",
                    "parameters": BKT_PARAMETERS,
                    "role": "secondary KT-form sensitivity only; prohibited from driving the scientific choice",
                    "known_generator_mismatch": [
                        "BKT averages active-KC mastery whereas the baseline generator uses weakest-link minimum aggregation.",
                        "BKT assigns the complete item outcome to every active KC and performs posterior-plus-learning updates, whereas the baseline generator gives all active KCs opportunity-based updates independent of correctness.",
                        "Consequently BKT performance mixes KC-representation sensitivity with deliberate response/update-model misspecification.",
                    ],
                },
            ],
            "same_observable_rows_within_world_across_representations_and_models": True,
            "interpretation_policy": "Primary KC robustness conclusions use the observable PFA/logistic. Empirical history and BKT are secondary sensitivity checks and cannot override the primary analysis.",
        },
        "evaluation": {
            "metrics": list(METRIC_NAMES),
            "delta_sign": "candidate_minus_true_kstar; positive favours K*",
            "reported_by_seed": True,
            "candidates": list(REPRESENTATION_ORDER[1:]),
            "reversals": [
                "representation rank order versus same-seed baseline world",
                "candidate-minus-K* metric sign versus same-seed baseline world",
                "candidate delta sign variation across seeds within condition",
            ],
        },
        "scientific_boundary": {
            "simulator_inputs": [
                "fixed item IDs/cell IDs",
                "fixed K* IDs",
                "fixed Q*",
                "fixed grammar-regime assignment",
                "frozen baseline measurement schedule",
                "declared downstream condition",
            ],
            "predictor_inputs": [
                "observable sensitivity interaction rows",
                "one outcome-free item-to-KC hypothesis",
            ],
            "observable_fields": list(OBSERVABLE_FIELDS),
            "derived_predictor_protocol_fields": [
                "updates_history := (phase == acquisition)"
            ],
            "frozen_baseline_interactions_read": False,
            "private_baseline_oracle_read": False,
            "private_sensitivity_event_state_emitted": False,
            "generator_truth_use": "world generation and the declared K* reference representation only",
        },
        "representations": representation_audits,
        "projection_bundle": {
            "path": projection_path.name,
            "sha256": _sha256_bytes(projection_payload.encode("utf-8")),
            "rows": len(fixed["items"]) * len(REPRESENTATION_ORDER),
        },
        "inputs": _plan_inputs(dataset_dir),
        "implementation": {
            "files": _implementation_hashes(),
            "repository_head_at_plan": _repository_head(),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "exact_commands": {
            "plan": ".venv/bin/python scripts/experiments/simulator_robustness.py --stage plan",
            "run": ".venv/bin/python scripts/experiments/simulator_robustness.py --stage run",
        },
    }
    _write_frozen_json(output_dir / "study_plan.json", plan, "study plan")
    return plan


def _validate_plan(
    dataset_dir: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, tuple[str, ...]]]]:
    plan_path = output_dir / "study_plan.json"
    projection_path = output_dir / "projections.jsonl"
    if not plan_path.is_file() or not projection_path.is_file():
        raise FileNotFoundError("run requires study_plan.json and projections.jsonl")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("study_id") != STUDY_ID:
        raise ValueError("study plan ID changed")
    if plan.get("status") != "PLANNED_BEFORE_RESPONSE_GENERATION":
        raise ValueError("study plan status changed")
    if plan["execution_design"]["conditions"] != planned_conditions():
        raise ValueError("planned condition definitions changed")
    if plan["execution_design"]["learners_per_world"] != LEARNERS:
        raise ValueError("planned learner count changed")
    if plan["execution_design"]["seeds"] != list(SEEDS):
        raise ValueError("planned seed set changed")
    if plan["implementation"]["files"] != _implementation_hashes():
        raise ValueError("implementation changed after plan")
    if plan["inputs"] != _plan_inputs(dataset_dir):
        raise ValueError("frozen inputs changed after plan")
    if plan["projection_bundle"]["sha256"] != file_sha256(projection_path):
        raise ValueError("projection bundle changed after plan")
    projections = _load_projection_bundle(projection_path)
    return plan, projections


def _observable_event_sha256(events: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in events:
        if tuple(row) != OBSERVABLE_FIELDS:
            raise ValueError(
                "predictor event contains non-observable, missing, or reordered fields"
            )
        digest.update(_canonical_json(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _secondary_probabilities(
    events: Sequence[Mapping[str, Any]],
    projection: Mapping[str, Sequence[str]],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Produce transparent empirical-history and deliberately simple BKT probes."""

    event_items = {str(row["item_id"]) for row in events}
    if event_items - set(projection):
        raise ValueError("secondary predictor projection lacks event items")
    learner_attempts: Counter[str] = Counter()
    learner_correct: Counter[str] = Counter()
    kc_attempts: Counter[tuple[str, str]] = Counter()
    kc_correct: Counter[tuple[str, str]] = Counter()
    bkt_state: dict[str, dict[str, float]] = defaultdict(dict)
    empirical_probe: list[float] = []
    bkt_probe: list[float] = []
    acquisition_events = 0
    probe_events = 0

    for event in events:
        learner_id = str(event["learner_id"])
        active = tuple(str(kc_id) for kc_id in projection[str(event["item_id"])])
        overall = (learner_correct[learner_id] + EMPIRICAL_ALPHA) / (
            learner_attempts[learner_id] + EMPIRICAL_ALPHA + EMPIRICAL_BETA
        )
        if active:
            empirical_probability = fmean(
                (kc_correct[(learner_id, kc_id)] + EMPIRICAL_ALPHA)
                / (
                    kc_attempts[(learner_id, kc_id)]
                    + EMPIRICAL_ALPHA
                    + EMPIRICAL_BETA
                )
                for kc_id in active
            )
            mean_mastery = fmean(
                bkt_state[learner_id].get(
                    kc_id, BKT_PARAMETERS["initial_mastery"]
                )
                for kc_id in active
            )
            bkt_probability = BKT_PARAMETERS["guess"] + (
                1.0 - BKT_PARAMETERS["slip"] - BKT_PARAMETERS["guess"]
            ) * mean_mastery
        else:
            empirical_probability = overall
            bkt_probability = overall

        if event["phase"] == "probe":
            empirical_probe.append(float(empirical_probability))
            bkt_probe.append(float(bkt_probability))
            probe_events += 1
            continue
        if event["phase"] != "acquisition":
            raise ValueError(f"unknown event phase: {event['phase']}")
        acquisition_events += 1
        correct = int(event["correct"])
        learner_attempts[learner_id] += 1
        learner_correct[learner_id] += correct
        for kc_id in active:
            kc_attempts[(learner_id, kc_id)] += 1
            kc_correct[(learner_id, kc_id)] += correct
            prior = bkt_state[learner_id].get(
                kc_id, BKT_PARAMETERS["initial_mastery"]
            )
            if correct:
                posterior = prior * (1.0 - BKT_PARAMETERS["slip"]) / (
                    prior * (1.0 - BKT_PARAMETERS["slip"])
                    + (1.0 - prior) * BKT_PARAMETERS["guess"]
                )
            else:
                posterior = prior * BKT_PARAMETERS["slip"] / (
                    prior * BKT_PARAMETERS["slip"]
                    + (1.0 - prior) * (1.0 - BKT_PARAMETERS["guess"])
                )
            bkt_state[learner_id][kc_id] = posterior + (
                1.0 - posterior
            ) * BKT_PARAMETERS["learn"]

    return (
        np.asarray(empirical_probe, dtype=float),
        np.asarray(bkt_probe, dtype=float),
        {
            "acquisition_events": acquisition_events,
            "probe_events": probe_events,
            "empirical_alpha": EMPIRICAL_ALPHA,
            "empirical_beta": EMPIRICAL_BETA,
            "bkt_parameters": dict(BKT_PARAMETERS),
            "bkt_known_generator_mismatch": True,
        },
    )


def _model_result(
    metrics: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    comparisons = []
    reference = metrics[REFERENCE_REPRESENTATION]
    for candidate_id in REPRESENTATION_ORDER[1:]:
        candidate = metrics[candidate_id]
        comparisons.append(
            {
                "candidate_representation": candidate_id,
                "reference_representation": REFERENCE_REPRESENTATION,
                "delta_sign": "candidate_minus_true_kstar; positive favours K*",
                "delta_log_loss": candidate["log_loss"] - reference["log_loss"],
                "delta_brier_score": candidate["brier_score"]
                - reference["brier_score"],
            }
        )
    rankings = {
        metric: sorted(
            REPRESENTATION_ORDER,
            key=lambda representation_id: (
                metrics[representation_id][metric],
                representation_id,
            ),
        )
        for metric in METRIC_NAMES
    }
    return {
        "metrics": dict(metrics),
        "comparisons": comparisons,
        "rankings": rankings,
    }


def evaluate_representations(
    events: Sequence[dict[str, Any]],
    projections: Mapping[str, Mapping[str, Sequence[str]]],
) -> dict[str, Any]:
    """Evaluate three observable models on one shared event object."""

    observable_sha256 = _observable_event_sha256(events)
    probe_targets = np.asarray(
        [int(row["correct"]) for row in events if row["phase"] == "probe"],
        dtype=np.int8,
    )
    if not len(probe_targets):
        raise ValueError("representation evaluation requires terminal probes")
    logistic_events = [
        {**row, "updates_history": row["phase"] == "acquisition"}
        for row in events
    ]
    metrics_by_model: dict[str, dict[str, dict[str, Any]]] = {
        model_id: {} for model_id in MODEL_ORDER
    }
    for representation_id in REPRESENTATION_ORDER:
        probabilities, model_audit = fit_observable_logistic(
            logistic_events,
            dict(projections[representation_id]),
            random_seed=MODEL_SEED,
        )
        empirical, bkt, secondary_audit = _secondary_probabilities(
            events, projections[representation_id]
        )
        probability_by_model = {
            PRIMARY_MODEL: probabilities,
            EMPIRICAL_MODEL: empirical,
            BKT_MODEL: bkt,
        }
        for model_id, model_probabilities in probability_by_model.items():
            scored = prediction_metrics(probe_targets, model_probabilities)
            audit = (
                model_audit
                if model_id == PRIMARY_MODEL
                else {
                    **secondary_audit,
                    "role": "secondary_sensitivity_only",
                    "known_generator_mismatch": model_id == BKT_MODEL,
                }
            )
            metrics_by_model[model_id][representation_id] = {
                "probe_events": int(scored["n"]),
                "log_loss": float(scored["log_loss"]),
                "brier_score": float(scored["brier_score"]),
                "model_audit": audit,
                "observable_event_sha256": observable_sha256,
            }
    observed_hashes = {
        row["observable_event_sha256"]
        for model_metrics in metrics_by_model.values()
        for row in model_metrics.values()
    }
    if observed_hashes != {observable_sha256}:
        raise AssertionError("models/representations did not consume the same events")
    return {
        "observable_event_sha256": observable_sha256,
        "same_observable_rows_across_representations_and_models": True,
        "primary_model_id": PRIMARY_MODEL,
        "secondary_model_ids": [EMPIRICAL_MODEL, BKT_MODEL],
        "models": {
            model_id: _model_result(metrics_by_model[model_id])
            for model_id in MODEL_ORDER
        },
        "interpretation_policy": "Only the observable PFA/logistic is primary; empirical history and BKT are secondary sensitivity checks.",
        "bkt_generator_mismatch": {
            "mean_instead_of_minimum_multi_kc_response": True,
            "full_credit_outcome_update_instead_of_all_active_opportunity_update": True,
            "may_drive_scientific_choice": False,
        },
    }


def _sign(value: float, tolerance: float = 1e-12) -> str:
    if value > tolerance:
        return "positive"
    if value < -tolerance:
        return "negative"
    return "zero"


def _world_lookup(worlds: Sequence[Mapping[str, Any]]) -> dict[tuple[str, int], Mapping[str, Any]]:
    output = {
        (str(world["condition_id"]), int(world["seed"])): world for world in worlds
    }
    if len(output) != len(worlds):
        raise ValueError("world results contain duplicate condition/seed pairs")
    return output


def _comparison_rows(worlds: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    lookup = _world_lookup(worlds)
    baseline_id = planned_conditions()[0]["condition"]["condition_id"]
    rows: list[dict[str, Any]] = []
    for world in worlds:
        baseline = lookup[(baseline_id, int(world["seed"]))]
        for model_id in MODEL_ORDER:
            world_model = world["evaluation"]["models"][model_id]
            baseline_model = baseline["evaluation"]["models"][model_id]
            baseline_comparisons = {
                row["candidate_representation"]: row
                for row in baseline_model["comparisons"]
            }
            for comparison in world_model["comparisons"]:
                candidate_id = comparison["candidate_representation"]
                baseline_comparison = baseline_comparisons[candidate_id]
                row: dict[str, Any] = {
                    "model_id": model_id,
                    "analysis_role": (
                        "primary" if model_id == PRIMARY_MODEL else "secondary"
                    ),
                    "condition_id": world["condition_id"],
                    "seed": int(world["seed"]),
                    "candidate_representation": candidate_id,
                    "delta_log_loss": float(comparison["delta_log_loss"]),
                    "delta_brier_score": float(comparison["delta_brier_score"]),
                    "log_loss_sign": _sign(float(comparison["delta_log_loss"])),
                    "brier_score_sign": _sign(float(comparison["delta_brier_score"])),
                    "log_loss_sign_reversal_vs_baseline": _sign(
                        float(comparison["delta_log_loss"])
                    )
                    != _sign(float(baseline_comparison["delta_log_loss"])),
                    "brier_score_sign_reversal_vs_baseline": _sign(
                        float(comparison["delta_brier_score"])
                    )
                    != _sign(float(baseline_comparison["delta_brier_score"])),
                    "log_loss_rank_order": ">".join(
                        world_model["rankings"]["log_loss"]
                    ),
                    "brier_score_rank_order": ">".join(
                        world_model["rankings"]["brier_score"]
                    ),
                    "log_loss_rank_reversal_vs_baseline": world_model[
                        "rankings"
                    ]["log_loss"]
                    != baseline_model["rankings"]["log_loss"],
                    "brier_score_rank_reversal_vs_baseline": world_model[
                        "rankings"
                    ]["brier_score"]
                    != baseline_model["rankings"]["brier_score"],
                }
                rows.append(row)
    return rows


def _summarize(
    worlds: Sequence[Mapping[str, Any]],
    comparison_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in comparison_rows:
        grouped[
            (
                row["model_id"],
                row["condition_id"],
                row["candidate_representation"],
            )
        ].append(row)
    seed_delta_summary = []
    within_condition_seed_sign_variation = []
    for (model_id, condition_id, candidate_id), rows in grouped.items():
        summary: dict[str, Any] = {
            "model_id": model_id,
            "analysis_role": "primary" if model_id == PRIMARY_MODEL else "secondary",
            "condition_id": condition_id,
            "candidate_representation": candidate_id,
            "seeds": sorted(int(row["seed"]) for row in rows),
        }
        for metric in METRIC_NAMES:
            key = f"delta_{metric}"
            values = [float(row[key]) for row in rows]
            signs = sorted({_sign(value) for value in values})
            summary[key] = {
                "mean": fmean(values),
                "population_sd": pstdev(values),
                "minimum": min(values),
                "maximum": max(values),
                "signs": signs,
            }
            if len(signs) > 1:
                within_condition_seed_sign_variation.append(
                    {
                        "model_id": model_id,
                        "condition_id": condition_id,
                        "candidate_representation": candidate_id,
                        "metric": metric,
                        "signs": signs,
                    }
                )
        seed_delta_summary.append(summary)

    sign_reversals = []
    for row in comparison_rows:
        for metric in METRIC_NAMES:
            if row[f"{metric}_sign_reversal_vs_baseline"]:
                sign_reversals.append(
                    {
                        "model_id": row["model_id"],
                        "condition_id": row["condition_id"],
                        "seed": row["seed"],
                        "candidate_representation": row[
                            "candidate_representation"
                        ],
                        "metric": metric,
                        "condition_sign": row[f"{metric}_sign"],
                    }
                )
    rank_reversals = []
    seen_rank_keys: set[tuple[str, str, int, str]] = set()
    for row in comparison_rows:
        for metric in METRIC_NAMES:
            key = (
                str(row["model_id"]),
                str(row["condition_id"]),
                int(row["seed"]),
                metric,
            )
            if row[f"{metric}_rank_reversal_vs_baseline"] and key not in seen_rank_keys:
                seen_rank_keys.add(key)
                rank_reversals.append(
                    {
                        "model_id": row["model_id"],
                        "condition_id": row["condition_id"],
                        "seed": row["seed"],
                        "metric": metric,
                        "condition_rank_order": row[f"{metric}_rank_order"].split(">"),
                    }
                )

    return {
        "candidate_minus_kstar_by_condition_across_seeds": seed_delta_summary,
        "sign_reversals_vs_same_seed_baseline": sign_reversals,
        "rank_reversals_vs_same_seed_baseline": rank_reversals,
        "within_condition_seed_sign_variation": within_condition_seed_sign_variation,
        "counts": {
            "candidate_sign_reversals_vs_baseline": len(sign_reversals),
            "rank_reversals_vs_baseline": len(rank_reversals),
            "within_condition_seed_sign_variations": len(
                within_condition_seed_sign_variation
            ),
            "primary_candidate_sign_reversals_vs_baseline": sum(
                row["model_id"] == PRIMARY_MODEL for row in sign_reversals
            ),
            "primary_rank_reversals_vs_baseline": sum(
                row["model_id"] == PRIMARY_MODEL for row in rank_reversals
            ),
        },
        "interpretation_policy": "Only rows with analysis_role=primary drive the KC robustness interpretation.",
    }


def _render_comparison_csv(rows: Sequence[Mapping[str, Any]]) -> str:
    fieldnames = [
        "model_id",
        "analysis_role",
        "condition_id",
        "seed",
        "candidate_representation",
        "delta_log_loss",
        "delta_brier_score",
        "log_loss_sign",
        "brier_score_sign",
        "log_loss_sign_reversal_vs_baseline",
        "brier_score_sign_reversal_vs_baseline",
        "log_loss_rank_order",
        "brier_score_rank_order",
        "log_loss_rank_reversal_vs_baseline",
        "brier_score_rank_reversal_vs_baseline",
    ]
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def run_study(dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    plan, projections = _validate_plan(dataset_dir, output_dir)
    fixed = _load_fixed_inputs(dataset_dir)
    common_hashes_by_seed: dict[int, dict[str, str]] = {}
    worlds: list[dict[str, Any]] = []
    for condition_record in plan["execution_design"]["conditions"]:
        condition = SensitivityCondition.from_dict(condition_record["condition"])
        for seed in plan["execution_design"]["seeds"]:
            print(f"simulate {condition.condition_id} seed={seed}", flush=True)
            design_config = copy.deepcopy(fixed["design_config"])
            design_config["seed"] = int(seed)
            design_config["learners"] = LEARNERS
            events, simulation_audit = simulate_sensitivity(
                fixed["items"],
                fixed["generator_kc_ids"],
                fixed["true_projection"],
                fixed["regime_by_cell"],
                design_config,
                condition,
                acquisition_item_ids=None,
            )
            observed_common = simulation_audit["common_random_number_hashes"]
            if int(seed) not in common_hashes_by_seed:
                common_hashes_by_seed[int(seed)] = observed_common
            elif common_hashes_by_seed[int(seed)] != observed_common:
                raise AssertionError(
                    f"common keyed draws changed across conditions for seed {seed}"
                )
            print(
                f"fit 3 representations {condition.condition_id} seed={seed}",
                flush=True,
            )
            evaluation = evaluate_representations(events, projections)
            worlds.append(
                {
                    "world_id": f"{condition.condition_id}__seed_{seed}",
                    "condition_id": condition.condition_id,
                    "condition": condition.to_dict(),
                    "condition_rationale": condition_record["rationale"],
                    "seed": int(seed),
                    "simulation_audit": simulation_audit,
                    "evaluation": evaluation,
                }
            )
            del events

    comparison_rows = _comparison_rows(worlds)
    summary = _summarize(worlds, comparison_rows)
    results = {
        "study_id": STUDY_ID,
        "status": "FINAL_COMPACT_ROBUSTNESS_RESULT",
        "study_plan_sha256": file_sha256(output_dir / "study_plan.json"),
        "projection_bundle_sha256": file_sha256(output_dir / "projections.jsonl"),
        "scale": {
            "conditions": len(plan["execution_design"]["conditions"]),
            "seeds": len(SEEDS),
            "worlds": len(worlds),
            "learners_per_world": LEARNERS,
            "primary_logistic_fits": len(worlds) * len(REPRESENTATION_ORDER),
            "secondary_model_evaluations": len(worlds)
            * len(REPRESENTATION_ORDER)
            * 2,
            "events_per_world": sorted(
                {world["simulation_audit"]["events"] for world in worlds}
            ),
        },
        "scientific_boundary": {
            "frozen_baseline_interactions_read": False,
            "private_baseline_oracle_read": False,
            "private_sensitivity_event_state_emitted": False,
            "predictor_event_fields": list(OBSERVABLE_FIELDS),
            "derived_predictor_protocol_fields": [
                "updates_history := (phase == acquisition)"
            ],
            "same_observable_event_rows_within_world_across_representations_and_models": all(
                world["evaluation"][
                    "same_observable_rows_across_representations_and_models"
                ]
                for world in worlds
            ),
            "primary_model": PRIMARY_MODEL,
            "secondary_models": [EMPIRICAL_MODEL, BKT_MODEL],
            "bkt_may_drive_scientific_choice": False,
        },
        "common_random_numbers": {
            "verified_identical_across_conditions_within_each_seed": True,
            "hashes_by_seed": common_hashes_by_seed,
        },
        "world_results": worlds,
        "summary": summary,
        "interpretation_scope": "These are consequences within declared synthetic worlds and do not establish human cognitive KC truth.",
    }
    results_path = output_dir / "results.json"
    comparisons_path = output_dir / "seed_comparisons.csv"
    _write_frozen_json(results_path, results, "robustness results")
    _write_frozen_text(
        comparisons_path,
        _render_comparison_csv(comparison_rows),
        "seed comparison table",
    )
    run_manifest = {
        "study_id": STUDY_ID,
        "status": "COMPLETE",
        "artifacts": {
            "study_plan.json": file_sha256(output_dir / "study_plan.json"),
            "projections.jsonl": file_sha256(output_dir / "projections.jsonl"),
            "results.json": file_sha256(results_path),
            "seed_comparisons.csv": file_sha256(comparisons_path),
        },
        "inputs": plan["inputs"],
        "implementation": plan["implementation"],
        "exact_commands": plan["exact_commands"],
        "repository_head_at_run": _repository_head(),
    }
    _write_frozen_json(output_dir / "run_manifest.json", run_manifest, "run manifest")
    print(f"wrote {results_path}", flush=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("plan", "run"), required=True)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    dataset_dir = args.dataset_dir.resolve()
    output_dir = args.output_dir.resolve()
    if args.stage == "plan":
        plan = create_plan(dataset_dir, output_dir)
        print(
            f"planned {plan['execution_design']['worlds']} worlds and "
            f"{plan['execution_design']['primary_logistic_fits']} primary fits at {output_dir}",
            flush=True,
        )
        return 0
    run_study(dataset_dir, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
