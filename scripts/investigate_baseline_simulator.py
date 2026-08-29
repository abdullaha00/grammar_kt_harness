#!/usr/bin/env python3
"""Run an outcome-free pilot over explicit K*, Q*, items, and grammar regimes.

The pilot compares a small preregistered set of response aggregators, learning
updates, initial-mastery distributions, response-noise values, acquisition
schedules, and learning rates.  It uses keyed common random numbers so aligned
draws are stable across conditions.  Acquisition uses seen items only; one
terminal probe covers the complete bank and never changes mastery.

This is an assumption audit, not a KT or KC-recovery experiment.  It does not
accept K-hat, discovered KCs, learner histories, KT predictions, or outcomes
from another dataset.  The output reports admissible conditions and
parsimony tiers but deliberately makes no final baseline selection.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.io import read_jsonl, write_json


PILOT_ID = "baseline_simulator_assumptions_v1"
AGGREGATIONS = ("minimum", "product", "arithmetic_mean", "mean_logit")
LEARNING_RULES = (
    "all_active_opportunity",
    "correct_only",
    "incorrect_only",
)
PREREGISTERED_MASTERY_VECTORS = (
    (0.05,),
    (0.50,),
    (0.95,),
    (0.95, 0.05),
    (0.20, 0.80),
    (0.20, 0.50, 0.80),
    (0.50, 0.50),
    (0.50, 0.50, 0.50, 0.50),
)
Q_BALANCED_TARGETS = (12, 20, 30)
EXHAUSTIVE_PASSES = (1, 2)
RATE_GRID = (0.01, 0.02)
INITIAL_BETA_GRID = ((2.0, 2.0), (2.0, 3.0))
SYMMETRIC_GUESS_SLIP_GRID = (0.05, 0.10, 0.20)
REFERENCE_CONDITION = {
    "aggregation": "minimum",
    "learning_rule": "all_active_opportunity",
    "schedule_mode": "q_balanced",
    "target_opportunities_per_seen_kc": 20,
    "exhaustive_passes": None,
    "learning_rate": 0.02,
    "beta_alpha": 2.0,
    "beta_beta": 2.0,
    "guess": 0.10,
    "slip": 0.10,
}
GATE_DECLARATION = {
    "minimum_seen_kc_opportunities_per_learner": {
        "minimum": 12,
        "rationale": "Every acquired KC should receive repeated measurement.",
    },
    "initial_seen_median_probability": {
        "minimum": 0.25,
        "maximum": 0.60,
        "rationale": "Initial responses should avoid trivial floor/ceiling states.",
    },
    "terminal_seen_median_probability": {
        "minimum": 0.55,
        "maximum": 0.80,
        "rationale": "Terminal responses should remain informative rather than saturated.",
    },
    "median_seen_probability_gain": {
        "minimum": 0.10,
        "maximum": 0.30,
        "rationale": "Acquisition should create visible but non-pathological change.",
    },
    "fraction_terminal_seen_kc_states_above_0_95": {
        "maximum": 0.10,
        "rationale": "Most acquired latent states should not saturate.",
    },
    "unseen_value_only_kcs_unchanged": {
        "absolute_tolerance": 1e-12,
        "rationale": "KCs exclusive to unseen-value items receive no acquisition update.",
    },
}
REGIME_ALIASES = {
    "seen": "seen",
    "unseen_combination": "unseen_combination",
    "unseen_value": "unseen_value",
    "development": "seen",
    "compositional_holdout": "unseen_combination",
    "novel_feature_holdout": "unseen_value",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git_revision() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _keyed_rng(seed: int, *keys: object) -> np.random.Generator:
    payload = json.dumps(
        [seed, *keys], ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    entropy = np.frombuffer(digest, dtype="<u4").tolist()
    return np.random.default_rng(np.random.SeedSequence(entropy))


def aggregate_mastery(values: Sequence[float], aggregation: str) -> float:
    """Aggregate active K* mastery without referring to KC names or grammar."""

    if aggregation not in AGGREGATIONS:
        raise ValueError(f"unknown response aggregation: {aggregation}")
    if not values:
        raise ValueError("response aggregation needs at least one active KC")
    numeric = [float(value) for value in values]
    if any(not 0.0 < value < 1.0 for value in numeric):
        raise ValueError("pilot mastery values must lie strictly between zero and one")
    if aggregation == "minimum":
        return min(numeric)
    if aggregation == "product":
        return math.prod(numeric)
    if aggregation == "arithmetic_mean":
        return sum(numeric) / len(numeric)
    logits = [math.log(value / (1.0 - value)) for value in numeric]
    mean_logit = sum(logits) / len(logits)
    return 1.0 / (1.0 + math.exp(-mean_logit))


def _response_probability(
    mastery_values: Sequence[float],
    aggregation: str,
    guess: float,
    slip: float,
) -> tuple[float, float]:
    if guess < 0.0 or slip < 0.0 or guess + slip >= 1.0:
        raise ValueError("guess/slip must be non-negative and sum to less than one")
    aggregated = aggregate_mastery(mastery_values, aggregation)
    probability = guess + (1.0 - guess - slip) * aggregated
    return aggregated, probability


def _monotonicity_check(aggregation: str, tolerance: float = 1e-12) -> dict[str, Any]:
    grid = (0.05, 0.25, 0.50, 0.75, 0.95)
    failures = []
    comparisons = 0
    for row_count in (2, 3):
        for vector in itertools.product(grid, repeat=row_count):
            baseline = aggregate_mastery(vector, aggregation)
            for index, value in enumerate(vector):
                larger = next((point for point in grid if point > value), None)
                if larger is None:
                    continue
                changed = list(vector)
                changed[index] = larger
                comparisons += 1
                result = aggregate_mastery(changed, aggregation)
                if result + tolerance < baseline:
                    failures.append(
                        {"before": list(vector), "after": changed, "index": index}
                    )
    return {
        "passed": not failures,
        "comparisons": comparisons,
        "failure_count": len(failures),
        "failures": failures[:10],
    }


def _permutation_check(aggregation: str, tolerance: float = 1e-12) -> dict[str, Any]:
    comparisons = 0
    failures = []
    for vector in PREREGISTERED_MASTERY_VECTORS:
        expected = aggregate_mastery(vector, aggregation)
        for permuted in sorted(set(itertools.permutations(vector))):
            comparisons += 1
            actual = aggregate_mastery(permuted, aggregation)
            if not math.isclose(actual, expected, abs_tol=tolerance, rel_tol=0.0):
                failures.append({"vector": list(vector), "permutation": list(permuted)})
    return {
        "passed": not failures,
        "comparisons": comparisons,
        "failure_count": len(failures),
        "failures": failures[:10],
    }


def _row_count_invariance_check(
    aggregation: str, tolerance: float = 1e-12
) -> dict[str, Any]:
    comparisons = []
    for value in (0.05, 0.25, 0.50, 0.75, 0.95):
        one = aggregate_mastery([value], aggregation)
        for row_count in (2, 3, 5):
            repeated = aggregate_mastery([value] * row_count, aggregation)
            comparisons.append(
                {
                    "mastery": value,
                    "active_kc_count": row_count,
                    "one_kc": one,
                    "repeated_equal_kcs": repeated,
                    "absolute_difference": abs(repeated - one),
                }
            )
    return {
        "passed": all(
            row["absolute_difference"] <= tolerance for row in comparisons
        ),
        "comparisons": comparisons,
    }


def analytical_aggregation_comparison() -> dict[str, Any]:
    """Evaluate the four aggregators against fixed, outcome-free hard checks."""

    results = []
    for aggregation in AGGREGATIONS:
        vector_rows = []
        for vector in PREREGISTERED_MASTERY_VECTORS:
            aggregated, probability = _response_probability(
                vector, aggregation, 0.10, 0.10
            )
            vector_rows.append(
                {
                    "mastery_vector": list(vector),
                    "aggregated_mastery": aggregated,
                    "response_probability_at_guess_slip_0_10": probability,
                }
            )
        noncompensatory_value = aggregate_mastery([0.95, 0.05], aggregation)
        hard_checks = {
            "monotonicity": _monotonicity_check(aggregation),
            "permutation_invariance": _permutation_check(aggregation),
            "noncompensation_0_95_0_05_at_most_0_10": {
                "passed": noncompensatory_value <= 0.10 + 1e-12,
                "value": noncompensatory_value,
                "maximum": 0.10,
            },
            "equal_skill_row_count_invariance": _row_count_invariance_check(
                aggregation
            ),
        }
        admissible = all(row["passed"] for row in hard_checks.values())
        results.append(
            {
                "aggregation": aggregation,
                "preregistered_vectors": vector_rows,
                "hard_checks": hard_checks,
                "all_hard_checks_passed": admissible,
            }
        )
    return {
        "mastery_vectors": [list(row) for row in PREREGISTERED_MASTERY_VECTORS],
        "hard_check_policy": {
            "monotonicity": "Increasing one mastery cannot lower aggregation.",
            "permutation_invariance": "KC ordering cannot affect aggregation.",
            "noncompensation": "aggregate([0.95, 0.05]) <= 0.10.",
            "equal_skill_row_count_invariance": (
                "Repeating an equal mastery value across 1/2/3/5 active KCs "
                "cannot change aggregation."
            ),
        },
        "results": results,
        "admissible_aggregations": [
            row["aggregation"] for row in results if row["all_hard_checks_passed"]
        ],
    }


def _normalize_regime(value: object) -> str:
    if value not in REGIME_ALIASES:
        raise ValueError(f"unknown grammar regime: {value}")
    return REGIME_ALIASES[str(value)]


def normalize_inputs(
    items: Sequence[Mapping[str, Any]],
    generator_kcs: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    q_rows: Sequence[Mapping[str, Any]],
    grammar_regime_by_cell: Mapping[str, str],
) -> dict[str, Any]:
    """Retain only fixed structural fields and validate the K*/Q* boundary."""

    if not items:
        raise ValueError("simulator pilot needs a non-empty fixed item bank")
    normalized_items = []
    for index, row in enumerate(items):
        item_id = row.get("item_id")
        cell_id = row.get("cell_id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"item row {index} has an invalid item_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise ValueError(f"item {item_id} has an invalid cell_id")
        normalized_items.append({"item_id": item_id, "cell_id": cell_id})
    normalized_items.sort(key=lambda row: row["item_id"])
    item_ids = [row["item_id"] for row in normalized_items]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("fixed item bank contains duplicate item IDs")

    if isinstance(generator_kcs, Mapping):
        kc_rows = generator_kcs.get("kcs")
    else:
        kc_rows = generator_kcs
    if not isinstance(kc_rows, Sequence) or isinstance(kc_rows, (str, bytes)):
        raise ValueError("explicit generator K* must be a row sequence")
    raw_kc_ids = [row.get("id") for row in kc_rows]
    if not raw_kc_ids or any(
        not isinstance(kc_id, str) or not kc_id for kc_id in raw_kc_ids
    ):
        raise ValueError("explicit generator K* contains an invalid KC ID")
    kc_ids = sorted(raw_kc_ids)
    if len(kc_ids) != len(set(kc_ids)):
        raise ValueError("explicit generator K* contains duplicate KC IDs")

    item_by_id = {row["item_id"]: row for row in normalized_items}
    active_by_item: dict[str, tuple[str, ...]] = {}
    normalized_q = []
    for index, row in enumerate(q_rows):
        item_id = row.get("item_id")
        if item_id not in item_by_id:
            raise ValueError(f"Q* row {index} refers to unknown item: {item_id}")
        if item_id in active_by_item:
            raise ValueError(f"Q* contains duplicate item row: {item_id}")
        active = row.get("generator_kc_ids")
        if (
            not isinstance(active, Sequence)
            or isinstance(active, (str, bytes))
            or not active
            or any(not isinstance(kc_id, str) or not kc_id for kc_id in active)
        ):
            raise ValueError(f"Q* item {item_id} must activate at least one KC")
        active_ids = tuple(sorted(active))
        if len(active_ids) != len(set(active_ids)):
            raise ValueError(f"Q* item {item_id} contains duplicate KC edges")
        unknown = set(active_ids) - set(kc_ids)
        if unknown:
            raise ValueError(f"Q* item {item_id} has unknown KCs: {sorted(unknown)}")
        cell_id = item_by_id[item_id]["cell_id"]
        if row.get("cell_id", cell_id) != cell_id:
            raise ValueError(f"Q* cell_id disagrees with item bank: {item_id}")
        active_by_item[item_id] = active_ids
        normalized_q.append(
            {
                "item_id": item_id,
                "cell_id": cell_id,
                "generator_kc_ids": list(active_ids),
            }
        )
    if set(active_by_item) != set(item_ids):
        raise ValueError("Q* must contain exactly one row for every fixed item")
    unsupported = set(kc_ids) - {
        kc_id for active in active_by_item.values() for kc_id in active
    }
    if unsupported:
        raise ValueError(f"generator KCs have no Q* support: {sorted(unsupported)}")
    normalized_q.sort(key=lambda row: row["item_id"])

    item_cells = {row["cell_id"] for row in normalized_items}
    missing_regimes = item_cells - set(grammar_regime_by_cell)
    if missing_regimes:
        raise ValueError(
            f"fixed-item cells lack grammar regimes: {sorted(missing_regimes)}"
        )
    normalized_regimes = {
        cell_id: _normalize_regime(grammar_regime_by_cell[cell_id])
        for cell_id in sorted(item_cells)
    }
    observed_regimes = set(normalized_regimes.values())
    required_regimes = {"seen", "unseen_combination", "unseen_value"}
    if observed_regimes != required_regimes:
        raise ValueError(
            "fixed bank must instantiate seen, unseen_combination, and "
            f"unseen_value; observed={sorted(observed_regimes)}"
        )

    regimes_by_kc = {kc_id: set() for kc_id in kc_ids}
    for item in normalized_items:
        regime = normalized_regimes[item["cell_id"]]
        for kc_id in active_by_item[item["item_id"]]:
            regimes_by_kc[kc_id].add(regime)
    return {
        "items": normalized_items,
        "kc_ids": kc_ids,
        "q_rows": normalized_q,
        "active_by_item": active_by_item,
        "grammar_regime_by_cell": normalized_regimes,
        "seen_kc_ids": sorted(
            kc_id for kc_id, regimes in regimes_by_kc.items() if "seen" in regimes
        ),
        "unseen_value_only_kc_ids": sorted(
            kc_id
            for kc_id, regimes in regimes_by_kc.items()
            if regimes == {"unseen_value"}
        ),
        "regimes_by_kc": {
            kc_id: sorted(regimes) for kc_id, regimes in regimes_by_kc.items()
        },
    }


def _condition_key(condition: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        condition["aggregation"],
        condition["learning_rule"],
        condition["schedule_mode"],
        condition["target_opportunities_per_seen_kc"],
        condition["exhaustive_passes"],
        condition["learning_rate"],
        condition["beta_alpha"],
        condition["beta_beta"],
        condition["guess"],
        condition["slip"],
    )


def _condition_id(condition: Mapping[str, Any]) -> str:
    if condition["schedule_mode"] == "q_balanced":
        schedule = (
            "qbalanced-target-"
            f"{condition['target_opportunities_per_seen_kc']:02d}"
        )
    elif condition["schedule_mode"] == "exhaustive_passes":
        schedule = f"exhaustive-passes-{condition['exhaustive_passes']:02d}"
    else:
        raise ValueError(f"unknown schedule mode: {condition['schedule_mode']}")
    return (
        f"agg-{condition['aggregation']}__update-{condition['learning_rule']}"
        f"__schedule-{schedule}__rate-{condition['learning_rate']:.3f}"
        f"__beta-{condition['beta_alpha']:.1f}-{condition['beta_beta']:.1f}"
        f"__noise-{condition['guess']:.2f}"
    )


def build_conditions() -> list[dict[str, Any]]:
    """Construct and deduplicate the compact factor-at-a-time pilot grid."""

    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}

    def add(family: str, **changes: Any) -> None:
        condition = {**REFERENCE_CONDITION, **changes}
        key = _condition_key(condition)
        if key not in by_key:
            by_key[key] = {**condition, "families": []}
        if family not in by_key[key]["families"]:
            by_key[key]["families"].append(family)

    for aggregation in AGGREGATIONS:
        for learning_rule in LEARNING_RULES:
            add(
                "aggregation_by_learning_rule",
                aggregation=aggregation,
                learning_rule=learning_rule,
            )
    for rate in RATE_GRID:
        add("learning_rate", learning_rate=rate)
    for alpha, beta in INITIAL_BETA_GRID:
        add("initial_mastery_beta", beta_alpha=alpha, beta_beta=beta)
    for value in SYMMETRIC_GUESS_SLIP_GRID:
        add("symmetric_guess_slip", guess=value, slip=value)
    for target in Q_BALANCED_TARGETS:
        add(
            "schedule_semantics",
            schedule_mode="q_balanced",
            target_opportunities_per_seen_kc=target,
            exhaustive_passes=None,
        )
    for passes in EXHAUSTIVE_PASSES:
        add(
            "schedule_semantics",
            schedule_mode="exhaustive_passes",
            target_opportunities_per_seen_kc=None,
            exhaustive_passes=passes,
        )

    conditions = []
    for condition in by_key.values():
        condition["families"].sort()
        condition["condition_id"] = _condition_id(condition)
        conditions.append(condition)
    return sorted(conditions, key=lambda row: row["condition_id"])


def _ordered_items(
    items: Sequence[dict[str, str]],
    *,
    seed: int,
    learner_number: int,
    phase: str,
    pass_index: int,
) -> list[dict[str, str]]:
    return sorted(
        items,
        key=lambda item: (
            float(
                _keyed_rng(
                    seed,
                    "item_order",
                    learner_number,
                    phase,
                    pass_index,
                    item["item_id"],
                ).random()
            ),
            item["item_id"],
        ),
    )


def build_acquisition_schedule(
    seen_items: Sequence[dict[str, str]],
    seen_kc_ids: Sequence[str],
    active_by_item: Mapping[str, Sequence[str]],
    condition: Mapping[str, Any],
    *,
    seed: int,
    learner_number: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build one deterministic exhaustive or Q-balanced acquisition schedule.

    Q-balanced selection greedily chooses the item covering the largest number
    of currently deficient seen KCs.  Ties prefer the least-exposed item, then
    a keyed random rank, then item ID.  The loop ends as soon as every seen KC
    reaches the declared target; co-activation may overshoot other KCs.
    """

    if not seen_items or not seen_kc_ids:
        raise ValueError("acquisition scheduling needs seen items and seen KCs")
    seen_set = set(seen_kc_ids)
    item_exposures = Counter({item["item_id"]: 0 for item in seen_items})
    kc_opportunities = Counter({kc_id: 0 for kc_id in seen_kc_ids})
    schedule: list[dict[str, Any]] = []

    def append_item(item: dict[str, str], pass_index: int) -> None:
        item_id = item["item_id"]
        item_exposures[item_id] += 1
        active_seen = sorted(set(active_by_item[item_id]) & seen_set)
        if not active_seen:
            raise ValueError(f"seen item activates no seen KC: {item_id}")
        kc_opportunities.update(active_seen)
        schedule.append(
            {
                "item": item,
                "schedule_step": len(schedule) + 1,
                "pass_index": pass_index,
                "item_exposure_index": item_exposures[item_id],
            }
        )

    mode = condition["schedule_mode"]
    if mode == "exhaustive_passes":
        passes = condition["exhaustive_passes"]
        if (
            isinstance(passes, bool)
            or not isinstance(passes, int)
            or passes < 1
            or condition["target_opportunities_per_seen_kc"] is not None
        ):
            raise ValueError("exhaustive schedule needs positive passes and no target")
        for pass_index in range(1, passes + 1):
            ordered = _ordered_items(
                seen_items,
                seed=seed,
                learner_number=learner_number,
                phase="acquisition_exhaustive",
                pass_index=pass_index,
            )
            for item in ordered:
                append_item(item, pass_index)
    elif mode == "q_balanced":
        target = condition["target_opportunities_per_seen_kc"]
        if (
            isinstance(target, bool)
            or not isinstance(target, int)
            or target < 1
            or condition["exhaustive_passes"] is not None
        ):
            raise ValueError("Q-balanced schedule needs a positive target and no passes")
        maximum_steps = target * len(seen_kc_ids)
        while min(kc_opportunities.values()) < target:
            step = len(schedule) + 1
            scored = []
            for item in seen_items:
                item_id = item["item_id"]
                active_seen = set(active_by_item[item_id]) & seen_set
                deficit_reduction = sum(
                    kc_opportunities[kc_id] < target for kc_id in active_seen
                )
                if not deficit_reduction:
                    continue
                keyed_tie = float(
                    _keyed_rng(
                        seed,
                        "q_balanced_tie",
                        learner_number,
                        step,
                        item_id,
                    ).random()
                )
                scored.append(
                    (
                        -deficit_reduction,
                        item_exposures[item_id],
                        keyed_tie,
                        item_id,
                        item,
                    )
                )
            if not scored:
                raise ValueError("Q-balanced scheduler cannot reduce a seen-KC deficit")
            selected = min(scored)[-1]
            pseudo_pass = 1 + (len(schedule) // len(seen_items))
            append_item(selected, pseudo_pass)
            if len(schedule) > maximum_steps:
                raise AssertionError("Q-balanced scheduler exceeded its deficit bound")
    else:
        raise ValueError(f"unknown schedule mode: {mode}")

    exposure_values = list(item_exposures.values())
    opportunity_values = list(kc_opportunities.values())
    return schedule, {
        "schedule_mode": mode,
        "schedule_length": len(schedule),
        "kc_opportunities": dict(sorted(kc_opportunities.items())),
        "kc_opportunity_minimum": min(opportunity_values),
        "kc_opportunity_median": median(opportunity_values),
        "kc_opportunity_maximum": max(opportunity_values),
        "item_exposures": dict(sorted(item_exposures.items())),
        "item_exposure_minimum": min(exposure_values),
        "item_exposure_median": median(exposure_values),
        "item_exposure_maximum": max(exposure_values),
        "item_exposure_imbalance": max(exposure_values) - min(exposure_values),
    }


def _digest_row(digest: Any, row: Mapping[str, Any]) -> None:
    digest.update(
        json.dumps(
            row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )
    digest.update(b"\n")


def _rounded_mapping(values: Mapping[str, float]) -> dict[str, float]:
    return {key: round(values[key], 12) for key in sorted(values)}


def _gate_results(metrics: Mapping[str, Any]) -> dict[str, Any]:
    gates = {
        "minimum_seen_kc_opportunities_per_learner": (
            metrics["minimum_seen_kc_opportunities_per_learner"]
            >= GATE_DECLARATION["minimum_seen_kc_opportunities_per_learner"][
                "minimum"
            ]
        ),
        "initial_seen_median_probability": (
            GATE_DECLARATION["initial_seen_median_probability"]["minimum"]
            <= metrics["initial_seen_median_probability"]
            <= GATE_DECLARATION["initial_seen_median_probability"]["maximum"]
        ),
        "terminal_seen_median_probability": (
            GATE_DECLARATION["terminal_seen_median_probability"]["minimum"]
            <= metrics["terminal_seen_median_probability"]
            <= GATE_DECLARATION["terminal_seen_median_probability"]["maximum"]
        ),
        "median_seen_probability_gain": (
            GATE_DECLARATION["median_seen_probability_gain"]["minimum"]
            <= metrics["median_seen_probability_gain"]
            <= GATE_DECLARATION["median_seen_probability_gain"]["maximum"]
        ),
        "fraction_terminal_seen_kc_states_above_0_95": (
            metrics["fraction_terminal_seen_kc_states_above_0_95"]
            <= GATE_DECLARATION[
                "fraction_terminal_seen_kc_states_above_0_95"
            ]["maximum"]
        ),
        "unseen_value_only_kcs_unchanged": (
            metrics["unseen_value_only_kc_gate_applicable"]
            and metrics["maximum_unseen_value_only_kc_absolute_change"]
            <= GATE_DECLARATION["unseen_value_only_kcs_unchanged"][
                "absolute_tolerance"
            ]
        ),
        "seen_only_acquisition": metrics["seen_only_acquisition_verified"],
        "terminal_probes_non_updating": metrics[
            "terminal_non_updating_probe_verified"
        ],
    }
    return {
        "passed": all(gates.values()),
        "checks": gates,
        "failures": sorted(name for name, passed in gates.items() if not passed),
    }


def simulate_condition(
    normalized: Mapping[str, Any],
    condition: Mapping[str, Any],
    *,
    learners: int,
    seed: int,
    schedule_cache: dict[
        tuple[Any, ...], tuple[list[dict[str, Any]], dict[str, Any]]
    ]
    | None = None,
) -> dict[str, Any]:
    """Simulate one declared condition using keyed common random numbers."""

    if learners < 1:
        raise ValueError("pilot learner count must be positive")
    started = time.perf_counter()
    items = normalized["items"]
    kc_ids = normalized["kc_ids"]
    active_by_item = normalized["active_by_item"]
    regimes = normalized["grammar_regime_by_cell"]
    seen_kcs = normalized["seen_kc_ids"]
    unseen_only = normalized["unseen_value_only_kc_ids"]
    seen_items = [row for row in items if regimes[row["cell_id"]] == "seen"]
    if not seen_items:
        raise ValueError("seen-only acquisition has no fixed items")

    rate = float(condition["learning_rate"])
    alpha = float(condition["beta_alpha"])
    beta = float(condition["beta_beta"])
    guess = float(condition["guess"])
    slip = float(condition["slip"])
    aggregation = str(condition["aggregation"])
    learning_rule = str(condition["learning_rule"])
    if not 0.0 < rate < 1.0 or alpha <= 0.0 or beta <= 0.0:
        raise ValueError("invalid pilot learning-rate/beta condition")
    if learning_rule not in LEARNING_RULES:
        raise ValueError(f"unknown learning rule: {learning_rule}")

    observable_digest = hashlib.sha256()
    oracle_digest = hashlib.sha256()
    random_draw_digest = hashlib.sha256()
    schedule_digest = hashlib.sha256()
    initial_state_digest = hashlib.sha256()
    terminal_state_digest = hashlib.sha256()
    initial_probabilities: list[float] = []
    terminal_probabilities: list[float] = []
    probability_gains: list[float] = []
    terminal_seen_states: list[float] = []
    unseen_changes: list[float] = []
    phase_counts: Counter[str] = Counter()
    correct_counts: Counter[str] = Counter()
    state_update_count = 0
    acquisition_regimes: set[str] = set()
    terminal_non_updating = True
    kc_opportunity_values: list[int] = []
    item_exposure_values: list[int] = []
    item_exposure_imbalances: list[int] = []
    acquisition_schedule_lengths: list[int] = []
    first_learner_schedule_diagnostics: dict[str, Any] | None = None

    for learner_number in range(1, learners + 1):
        learner_id = f"pilot_learner_{learner_number:06d}"
        mastery = {
            kc_id: float(
                _keyed_rng(seed, "initial_mastery", learner_number, kc_id).beta(
                    alpha, beta
                )
            )
            for kc_id in kc_ids
        }
        initial_mastery = dict(mastery)
        _digest_row(
            initial_state_digest,
            {"learner_id": learner_id, "mastery": _rounded_mapping(mastery)},
        )
        initial_seen_by_item = {}
        for item in seen_items:
            active = active_by_item[item["item_id"]]
            _aggregated, probability = _response_probability(
                [mastery[kc_id] for kc_id in active], aggregation, guess, slip
            )
            initial_seen_by_item[item["item_id"]] = probability
            initial_probabilities.append(probability)

        schedule_key = (
            seed,
            learner_number,
            condition["schedule_mode"],
            condition["target_opportunities_per_seen_kc"],
            condition["exhaustive_passes"],
        )
        cached = schedule_cache.get(schedule_key) if schedule_cache is not None else None
        if cached is None:
            cached = build_acquisition_schedule(
                seen_items,
                seen_kcs,
                active_by_item,
                condition,
                seed=seed,
                learner_number=learner_number,
            )
            if schedule_cache is not None:
                schedule_cache[schedule_key] = cached
        acquisition_schedule, schedule_diagnostics = cached
        if first_learner_schedule_diagnostics is None:
            first_learner_schedule_diagnostics = schedule_diagnostics
        kc_opportunity_values.extend(
            schedule_diagnostics["kc_opportunities"].values()
        )
        item_exposure_values.extend(schedule_diagnostics["item_exposures"].values())
        item_exposure_imbalances.append(
            schedule_diagnostics["item_exposure_imbalance"]
        )
        acquisition_schedule_lengths.append(
            schedule_diagnostics["schedule_length"]
        )
        _digest_row(
            schedule_digest,
            {
                "learner_id": learner_id,
                "schedule": [
                    {
                        "schedule_step": row["schedule_step"],
                        "item_id": row["item"]["item_id"],
                        "pass_index": row["pass_index"],
                        "item_exposure_index": row["item_exposure_index"],
                    }
                    for row in acquisition_schedule
                ],
            },
        )

        sequence_index = 0
        for scheduled in acquisition_schedule:
            item = scheduled["item"]
            pass_index = scheduled["pass_index"]
            item_exposure_index = scheduled["item_exposure_index"]
            sequence_index += 1
            item_id = item["item_id"]
            active = active_by_item[item_id]
            before = {kc_id: mastery[kc_id] for kc_id in active}
            aggregated, probability = _response_probability(
                list(before.values()), aggregation, guess, slip
            )
            draw = float(
                _keyed_rng(
                    seed,
                    "response",
                    learner_number,
                    "acquisition",
                    item_id,
                    item_exposure_index,
                ).random()
            )
            correct = int(draw < probability)
            should_update = (
                learning_rule == "all_active_opportunity"
                or (learning_rule == "correct_only" and correct == 1)
                or (learning_rule == "incorrect_only" and correct == 0)
            )
            if should_update:
                for kc_id in active:
                    mastery[kc_id] += rate * (1.0 - mastery[kc_id])
                    state_update_count += 1
            after = {kc_id: mastery[kc_id] for kc_id in active}
            regime = regimes[item["cell_id"]]
            acquisition_regimes.add(regime)
            observable = {
                "learner_id": learner_id,
                "item_id": item_id,
                "sequence_index": sequence_index,
                "correct": correct,
                "phase": "acquisition",
                "pass_index": pass_index,
                "grammar_regime": regime,
            }
            oracle = {
                **observable,
                "schedule_mode": condition["schedule_mode"],
                "schedule_step": scheduled["schedule_step"],
                "item_exposure_index": item_exposure_index,
                "active_generator_kc_ids": list(active),
                "mastery_before": _rounded_mapping(before),
                "aggregated_mastery_before": round(aggregated, 12),
                "response_probability": round(probability, 12),
                "response_draw": round(draw, 12),
                "learning_rule": learning_rule,
                "updates_mastery": should_update,
                "mastery_after": _rounded_mapping(after),
            }
            _digest_row(observable_digest, observable)
            _digest_row(oracle_digest, oracle)
            _digest_row(
                random_draw_digest,
                {
                    "learner_id": learner_id,
                    "item_id": item_id,
                    "phase": "acquisition",
                    "item_exposure_index": item_exposure_index,
                    "draw": round(draw, 12),
                },
            )
            phase_counts["acquisition"] += 1
            correct_counts["acquisition"] += correct

        terminal_mastery = dict(mastery)
        _digest_row(
            terminal_state_digest,
            {
                "learner_id": learner_id,
                "mastery": _rounded_mapping(terminal_mastery),
            },
        )
        terminal_seen_states.extend(terminal_mastery[kc_id] for kc_id in seen_kcs)
        unseen_changes.extend(
            abs(terminal_mastery[kc_id] - initial_mastery[kc_id])
            for kc_id in unseen_only
        )
        for item in seen_items:
            active = active_by_item[item["item_id"]]
            _aggregated, probability = _response_probability(
                [terminal_mastery[kc_id] for kc_id in active],
                aggregation,
                guess,
                slip,
            )
            terminal_probabilities.append(probability)
            probability_gains.append(
                probability - initial_seen_by_item[item["item_id"]]
            )

        before_probe = dict(mastery)
        for item in _ordered_items(
            items,
            seed=seed,
            learner_number=learner_number,
            phase="probe",
            pass_index=1,
        ):
            sequence_index += 1
            item_id = item["item_id"]
            active = active_by_item[item_id]
            before = {kc_id: mastery[kc_id] for kc_id in active}
            aggregated, probability = _response_probability(
                list(before.values()), aggregation, guess, slip
            )
            draw = float(
                _keyed_rng(
                    seed,
                    "response",
                    learner_number,
                    "probe",
                    1,
                    item_id,
                ).random()
            )
            correct = int(draw < probability)
            regime = regimes[item["cell_id"]]
            observable = {
                "learner_id": learner_id,
                "item_id": item_id,
                "sequence_index": sequence_index,
                "correct": correct,
                "phase": "probe",
                "pass_index": 1,
                "grammar_regime": regime,
            }
            oracle = {
                **observable,
                "active_generator_kc_ids": list(active),
                "mastery_before": _rounded_mapping(before),
                "aggregated_mastery_before": round(aggregated, 12),
                "response_probability": round(probability, 12),
                "response_draw": round(draw, 12),
                "learning_rule": learning_rule,
                "updates_mastery": False,
                "mastery_after": _rounded_mapping(before),
            }
            _digest_row(observable_digest, observable)
            _digest_row(oracle_digest, oracle)
            _digest_row(
                random_draw_digest,
                {
                    "learner_id": learner_id,
                    "item_id": item_id,
                    "phase": "probe",
                    "pass_index": 1,
                    "draw": round(draw, 12),
                },
            )
            phase_counts["probe"] += 1
            correct_counts["probe"] += correct
        terminal_non_updating = terminal_non_updating and mastery == before_probe

    total_events = sum(phase_counts.values())
    metrics = {
        "minimum_seen_kc_opportunities_per_learner": min(kc_opportunity_values),
        "seen_kc_opportunities_per_learner": {
            "minimum": min(kc_opportunity_values),
            "median": median(kc_opportunity_values),
            "maximum": max(kc_opportunity_values),
        },
        "seen_item_exposures_per_learner": {
            "minimum": min(item_exposure_values),
            "median": median(item_exposure_values),
            "maximum": max(item_exposure_values),
        },
        "item_exposure_imbalance_per_learner": {
            "minimum": min(item_exposure_imbalances),
            "median": median(item_exposure_imbalances),
            "maximum": max(item_exposure_imbalances),
        },
        "acquisition_schedule_length_per_learner": {
            "minimum": min(acquisition_schedule_lengths),
            "median": median(acquisition_schedule_lengths),
            "maximum": max(acquisition_schedule_lengths),
        },
        "first_learner_schedule_diagnostics": first_learner_schedule_diagnostics,
        "initial_seen_median_probability": median(initial_probabilities),
        "terminal_seen_median_probability": median(terminal_probabilities),
        "median_seen_probability_gain": median(probability_gains),
        "fraction_terminal_seen_kc_states_above_0_95": (
            sum(value > 0.95 for value in terminal_seen_states)
            / len(terminal_seen_states)
        ),
        "unseen_value_only_kc_gate_applicable": bool(unseen_only),
        "unseen_value_only_kc_ids": unseen_only,
        "maximum_unseen_value_only_kc_absolute_change": (
            max(unseen_changes) if unseen_changes else None
        ),
        "seen_only_acquisition_verified": acquisition_regimes == {"seen"},
        "terminal_non_updating_probe_verified": terminal_non_updating,
        "event_counts": {
            "total": total_events,
            "acquisition": phase_counts["acquisition"],
            "terminal_probe": phase_counts["probe"],
        },
        "response_rates": {
            phase: correct_counts[phase] / phase_counts[phase]
            for phase in ("acquisition", "probe")
        },
        "latent_state_update_count": state_update_count,
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "hashes": {
            "observable_events_sha256": observable_digest.hexdigest(),
            "oracle_events_sha256": oracle_digest.hexdigest(),
            "common_random_draws_sha256": random_draw_digest.hexdigest(),
            "acquisition_schedules_sha256": schedule_digest.hexdigest(),
            "initial_mastery_states_sha256": initial_state_digest.hexdigest(),
            "terminal_mastery_states_sha256": terminal_state_digest.hexdigest(),
        },
    }
    gates = _gate_results(metrics)
    return {"metrics": metrics, "simulation_gates": gates}


def _parsimony_tiers(
    conditions: Sequence[Mapping[str, Any]], admissible_ids: set[str]
) -> dict[str, Any]:
    aggregation_tier = {
        "minimum": 1,
        "product": 1,
        "arithmetic_mean": 1,
        "mean_logit": 2,
    }
    learning_tier = {
        "all_active_opportunity": 1,
        "correct_only": 2,
        "incorrect_only": 2,
    }
    schedule_tier = {"exhaustive_passes": 1, "q_balanced": 2}
    groups: dict[tuple[int, int, int], list[str]] = {}
    for condition in conditions:
        condition_id = condition["condition_id"]
        if condition_id not in admissible_ids:
            continue
        key = (
            aggregation_tier[condition["aggregation"]],
            learning_tier[condition["learning_rule"]],
            schedule_tier[condition["schedule_mode"]],
        )
        groups.setdefault(key, []).append(condition_id)
    return {
        "principle": (
            "Tiers count transformation and outcome-conditioning complexity; "
            "they do not select a scientifically final condition."
        ),
        "aggregation": [
            {
                "tier": 1,
                "conditions": ["minimum", "product", "arithmetic_mean"],
                "rationale": "One direct symmetric reduction over active mastery.",
            },
            {
                "tier": 2,
                "conditions": ["mean_logit"],
                "rationale": "Adds logit and inverse-logit transformations.",
            },
        ],
        "learning_update": [
            {
                "tier": 1,
                "conditions": ["all_active_opportunity"],
                "rationale": "No response-outcome branch in the learning rule.",
            },
            {
                "tier": 2,
                "conditions": ["correct_only", "incorrect_only"],
                "rationale": "Adds one declared response-outcome branch.",
            },
        ],
        "schedule": [
            {
                "tier": 1,
                "conditions": ["exhaustive_passes"],
                "rationale": "Repeat every seen item with no Q-aware targeting.",
            },
            {
                "tier": 2,
                "conditions": ["q_balanced"],
                "rationale": "Adds Q-aware deficit tracking and greedy item choice.",
            },
        ],
        "admissible_condition_tiers": [
            {
                "aggregation_tier": key[0],
                "learning_update_tier": key[1],
                "schedule_tier": key[2],
                "condition_ids": sorted(condition_ids),
            }
            for key, condition_ids in sorted(groups.items())
        ],
    }


def investigate_baseline_simulator(
    items: Sequence[Mapping[str, Any]],
    generator_kcs: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    q_rows: Sequence[Mapping[str, Any]],
    grammar_regime_by_cell: Mapping[str, str],
    *,
    learners: int = 128,
    seed: int = 20260829,
    input_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the analytical audit and compact CRN condition grid."""

    started = time.perf_counter()
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("pilot seed must be a non-negative integer")
    normalized = normalize_inputs(items, generator_kcs, q_rows, grammar_regime_by_cell)
    analytical = analytical_aggregation_comparison()
    analytically_admissible = set(analytical["admissible_aggregations"])
    conditions = build_conditions()
    results = []
    schedule_cache: dict[
        tuple[Any, ...], tuple[list[dict[str, Any]], dict[str, Any]]
    ] = {}
    for condition in conditions:
        simulation = simulate_condition(
            normalized,
            condition,
            learners=learners,
            seed=seed,
            schedule_cache=schedule_cache,
        )
        analytically_passed = condition["aggregation"] in analytically_admissible
        admissible = analytically_passed and simulation["simulation_gates"]["passed"]
        failures = list(simulation["simulation_gates"]["failures"])
        if not analytically_passed:
            failures.append("aggregation_hard_checks")
        results.append(
            {
                **condition,
                **simulation,
                "analytical_aggregation_gates_passed": analytically_passed,
                "admissible": admissible,
                "admissibility_failures": sorted(failures),
            }
        )
    admissible_ids = {
        row["condition_id"] for row in results if row["admissible"]
    }
    schedule_comparison = []
    for row in results:
        if "schedule_semantics" not in row["families"]:
            continue
        metrics = row["metrics"]
        schedule_comparison.append(
            {
                "condition_id": row["condition_id"],
                "schedule_mode": row["schedule_mode"],
                "target_opportunities_per_seen_kc": row[
                    "target_opportunities_per_seen_kc"
                ],
                "exhaustive_passes": row["exhaustive_passes"],
                "seen_kc_opportunities_per_learner": metrics[
                    "seen_kc_opportunities_per_learner"
                ],
                "seen_item_exposures_per_learner": metrics[
                    "seen_item_exposures_per_learner"
                ],
                "item_exposure_imbalance_per_learner": metrics[
                    "item_exposure_imbalance_per_learner"
                ],
                "acquisition_schedule_length_per_learner": metrics[
                    "acquisition_schedule_length_per_learner"
                ],
                "initial_seen_median_probability": metrics[
                    "initial_seen_median_probability"
                ],
                "terminal_seen_median_probability": metrics[
                    "terminal_seen_median_probability"
                ],
                "median_seen_probability_gain": metrics[
                    "median_seen_probability_gain"
                ],
                "event_counts": metrics["event_counts"],
                "simulation_gates": row["simulation_gates"],
                "admissible": row["admissible"],
            }
        )
    structural_inputs = {
        "items": normalized["items"],
        "generator_kc_ids": normalized["kc_ids"],
        "q_rows": normalized["q_rows"],
        "grammar_regime_by_cell": normalized["grammar_regime_by_cell"],
    }
    return {
        "pilot_id": PILOT_ID,
        "scientific_boundary": {
            "inputs_consumed": [
                "fixed_items",
                "explicit_generator_k_star",
                "deterministic_q_star",
                "grammar_regimes",
            ],
            "item_fields_consumed": ["item_id", "cell_id"],
            "inputs_not_accepted": [
                "k_hat",
                "discovered_kcs",
                "learner_outcomes",
                "kt_predictions",
                "kc_recovery_metrics",
            ],
            "prediction_or_kc_recovery_used": False,
            "baseline_config_modified": False,
            "baseline_simulator_modified": False,
        },
        "protocol": {
            "learners": learners,
            "seed": seed,
            "rng": {
                "scheme": "keyed_sha256_v1",
                "common_random_number_keys": [
                    "initial_mastery: learner + generator KC",
                    "exhaustive order: learner + pass + item",
                    "Q-balanced tie: learner + schedule step + item",
                    "acquisition response: learner + item + item exposure index",
                    "probe response: learner + probe repeat + item",
                ],
                "condition_values_excluded_from_draw_keys": True,
                "alignment_scope": (
                    "Conditions with the same schedule share the complete draw "
                    "sequence. Across schedule modes, the same learner/item/exposure "
                    "uses the same response draw, but event sequence and exposure "
                    "sets can differ."
                ),
            },
            "schedule": {
                "acquisition_regime": "seen",
                "modes": {
                    "q_balanced": {
                        "targets_per_seen_kc": list(Q_BALANCED_TARGETS),
                        "algorithm": (
                            "Greedily maximize currently deficient KC coverage; "
                            "then minimize prior item exposure; then keyed random "
                            "tie-break; then item ID."
                        ),
                    },
                    "exhaustive_passes": {
                        "passes": list(EXHAUSTIVE_PASSES),
                        "algorithm": "Present every seen item once per keyed pass.",
                    },
                },
                "probe_timing": "terminal",
                "probe_repeats": 1,
                "probe_item_scope": "all_regimes",
                "probe_updates_mastery": False,
                "balanced_pass_index_semantics": (
                    "For audit rows only, pass_index is the one-based pseudo-cycle "
                    "ceil(schedule_step / seen_item_count); random draws use the "
                    "item exposure index instead."
                ),
            },
            "aggregation_values": list(AGGREGATIONS),
            "learning_rules": list(LEARNING_RULES),
            "learning_rates": list(RATE_GRID),
            "initial_mastery_beta": [list(row) for row in INITIAL_BETA_GRID],
            "symmetric_guess_slip": list(SYMMETRIC_GUESS_SLIP_GRID),
            "reference_condition": REFERENCE_CONDITION,
            "condition_design": (
                "Aggregation x learning-rule factorial at Q-balanced target 20, "
                "plus factor-at-a-time schedule, rate, beta, and guess/slip grids."
            ),
            "condition_count": len(conditions),
            "gate_declaration": GATE_DECLARATION,
            "gate_declaration_status": (
                "independently_preregistered_nonpathology_criteria"
            ),
        },
        "inputs": {
            "item_count": len(normalized["items"]),
            "generator_kc_count": len(normalized["kc_ids"]),
            "q_edge_count": sum(
                len(row["generator_kc_ids"]) for row in normalized["q_rows"]
            ),
            "grammar_regime_item_counts": dict(
                sorted(
                    Counter(
                        normalized["grammar_regime_by_cell"][row["cell_id"]]
                        for row in normalized["items"]
                    ).items()
                )
            ),
            "seen_kc_ids": normalized["seen_kc_ids"],
            "unseen_value_only_kc_ids": normalized[
                "unseen_value_only_kc_ids"
            ],
            "logical_sha256": _json_sha256(structural_inputs),
            **dict(input_metadata or {}),
        },
        "analytical_aggregation_comparison": analytical,
        "condition_grid_sha256": _json_sha256(conditions),
        "conditions": results,
        "schedule_comparison": schedule_comparison,
        "admissible_condition_ids": sorted(admissible_ids),
        "parsimony_ordering": _parsimony_tiers(results, admissible_ids),
        "selection": {
            "selected_condition_id": None,
            "reason": (
                "This pilot reports hard-gate admissibility and parsimony tiers; "
                "the generator methodology must make and document the final choice."
            ),
        },
        "runtime": {
            "conditions_executed": len(results),
            "total_events": sum(
                row["metrics"]["event_counts"]["total"] for row in results
            ),
            "wall_seconds": round(time.perf_counter() - started, 6),
        },
    }


def _read_json_value(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_generator_kcs(path: Path) -> list[dict[str, Any]] | dict[str, Any]:
    if path.suffix == ".jsonl":
        return read_jsonl(path)
    value = _read_json_value(path)
    if not isinstance(value, (list, dict)):
        raise ValueError("generator K* file must contain a list or inventory object")
    return value


def _read_q_rows(path: Path, items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if path.suffix != ".csv":
        value = read_jsonl(path) if path.suffix == ".jsonl" else _read_json_value(path)
        if isinstance(value, dict):
            value = value.get("q_rows") or value.get("rows")
        if not isinstance(value, list):
            raise ValueError("sparse Q* file must contain a row list")
        return value

    cell_by_item = {row["item_id"]: row["cell_id"] for row in items}
    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "item_id" not in reader.fieldnames:
            raise ValueError("dense Q* CSV needs an item_id column")
        kc_columns = [
            name for name in reader.fieldnames if name not in {"item_id", "cell_id"}
        ]
        for row in reader:
            item_id = row["item_id"]
            active = []
            for kc_id in kc_columns:
                value = str(row[kc_id]).strip().lower()
                if value in {"1", "1.0", "true"}:
                    active.append(kc_id)
                elif value not in {"0", "0.0", "false", ""}:
                    raise ValueError(f"Q* CSV has non-binary value: {kc_id}={value}")
            rows.append(
                {
                    "item_id": item_id,
                    "cell_id": row.get("cell_id") or cell_by_item.get(item_id),
                    "generator_kc_ids": active,
                }
            )
    return rows


def _read_regimes(path: Path) -> dict[str, str]:
    value: Any = read_jsonl(path) if path.suffix == ".jsonl" else _read_json_value(path)
    if isinstance(value, dict):
        if "rows" in value:
            value = value["rows"]
        elif all(isinstance(key, str) for key in value):
            return {str(key): str(regime) for key, regime in value.items()}
    if not isinstance(value, list):
        raise ValueError("grammar regimes must be a cell mapping or row list")
    output = {}
    for row in value:
        cell_id = row.get("cell_id")
        regime = row.get("grammar_regime", row.get("grammar_split"))
        if not isinstance(cell_id, str) or not isinstance(regime, str):
            raise ValueError("grammar regime rows need cell_id and regime")
        if cell_id in output:
            raise ValueError(f"duplicate grammar regime row: {cell_id}")
        output[cell_id] = regime
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--kcs", type=Path, required=True)
    parser.add_argument("--q-matrix", type=Path, required=True)
    parser.add_argument("--regimes", type=Path, required=True)
    parser.add_argument("--learners", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260829)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.learners < 1 or arguments.seed < 0:
        parser.error("learners must be positive and seed non-negative")
    return arguments


def main() -> int:
    arguments = parse_args()
    paths = {
        "items_path": arguments.items.resolve(),
        "generator_kcs_path": arguments.kcs.resolve(),
        "q_matrix_path": arguments.q_matrix.resolve(),
        "grammar_regimes_path": arguments.regimes.resolve(),
    }
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"{name} does not exist: {path}")
    items = read_jsonl(paths["items_path"])
    kcs = _read_generator_kcs(paths["generator_kcs_path"])
    q_rows = _read_q_rows(paths["q_matrix_path"], items)
    regimes = _read_regimes(paths["grammar_regimes_path"])
    input_metadata = {
        name: _display_path(path) for name, path in paths.items()
    } | {
        f"{name.removesuffix('_path')}_file_sha256": _sha256_file(path)
        for name, path in paths.items()
    }
    script_path = Path(__file__).resolve()
    input_metadata.update(
        {
            "script_path": _display_path(script_path),
            "script_sha256": _sha256_file(script_path),
            "git_revision": _git_revision(),
            "exact_command": " ".join([sys.executable, *sys.argv]),
        }
    )
    artifact = investigate_baseline_simulator(
        items,
        kcs,
        q_rows,
        regimes,
        learners=arguments.learners,
        seed=arguments.seed,
        input_metadata=input_metadata,
    )
    write_json(arguments.output, artifact)
    print(
        json.dumps(
            {
                "output": str(arguments.output.resolve()),
                "conditions": artifact["runtime"]["conditions_executed"],
                "events": artifact["runtime"]["total_events"],
                "admissible_conditions": len(artifact["admissible_condition_ids"]),
                "wall_seconds": artifact["runtime"]["wall_seconds"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
