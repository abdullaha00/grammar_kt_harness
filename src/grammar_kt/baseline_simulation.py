"""Baseline learner simulation over an explicit generator K* and true Q*.

The simulator is deliberately narrower than the historical latent-world
simulator.  It consumes a fixed item bank, the already-frozen generator KC
inventory, and an already-built Q-matrix.  It does not inspect GrammarCell
features, discovered KCs, learner outcomes, item difficulty, or background
mastery.

Random quantities use stable keyed streams.  Consequently, adding learners
does not change an existing learner's trajectory, input row order does not
change the schedule, and terminal probe draws do not depend on probe order.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from statistics import median
from typing import Any

import numpy as np


OBSERVABLE_FIELDS = (
    "learner_id",
    "item_id",
    "sequence_index",
    "correct",
    "phase",
    "pass_index",
    "grammar_regime",
)

ORACLE_FIELDS = (
    "learner_id",
    "item_id",
    "sequence_index",
    "phase",
    "pass_index",
    "grammar_regime",
    "active_generator_kc_ids",
    "mastery_before",
    "aggregated_mastery_before",
    "response_probability",
    "response_draw",
    "correct",
    "updates_mastery",
    "mastery_after",
)


def _required(mapping: Mapping[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise ValueError(f"{context} is missing required field: {key}")
    return mapping[key]


def _exact_keys(
    mapping: Mapping[str, Any], expected: set[str], context: str
) -> None:
    actual = set(mapping)
    if actual != expected:
        raise ValueError(
            f"{context} fields differ: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _positive_int(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{context} must be a positive integer")
    return value


def _finite_number(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{context} must be finite")
    return result


def validate_baseline_config(config: Mapping[str, Any]) -> None:
    """Reject configuration that changes the declared baseline semantics."""

    _exact_keys(
        config,
        {
            "simulation_id",
            "description",
            "seed",
            "learners",
            "initial_mastery",
            "response",
            "learning",
            "schedule",
            "rng",
            "learner_ids",
            "observable_schema",
            "oracle_mastery_scope",
        },
        "simulation config",
    )
    if not isinstance(config["simulation_id"], str) or not config["simulation_id"]:
        raise ValueError("simulation_id must be a non-empty string")
    if not isinstance(config["description"], str) or not config["description"]:
        raise ValueError("description must be a non-empty string")
    configured_seed = config["seed"]
    if (
        isinstance(configured_seed, bool)
        or not isinstance(configured_seed, int)
        or configured_seed < 0
    ):
        raise ValueError("seed must be a non-negative integer")

    _positive_int(_required(config, "learners", "simulation config"), "learners")

    initial = _required(config, "initial_mastery", "simulation config")
    _exact_keys(
        initial,
        {"distribution", "alpha", "beta", "background_mastery"},
        "initial_mastery",
    )
    if initial.get("distribution") != "beta":
        raise ValueError("baseline initial mastery distribution must be beta")
    beta_alpha = _finite_number(
        _required(initial, "alpha", "initial_mastery"),
        "initial_mastery.alpha",
    )
    beta_beta = _finite_number(
        _required(initial, "beta", "initial_mastery"),
        "initial_mastery.beta",
    )
    if beta_alpha <= 0.0 or beta_beta <= 0.0:
        raise ValueError("initial mastery beta parameters must be positive")
    if initial.get("background_mastery") != "none":
        raise ValueError("baseline simulation has no background mastery")

    response = _required(config, "response", "simulation config")
    _exact_keys(
        response,
        {"aggregation", "guess", "slip", "item_difficulty"},
        "response",
    )
    if response.get("aggregation") != "minimum":
        raise ValueError("baseline response aggregation must be minimum")
    guess = _finite_number(
        _required(response, "guess", "response"), "response.guess"
    )
    slip = _finite_number(
        _required(response, "slip", "response"), "response.slip"
    )
    if guess < 0.0 or slip < 0.0 or guess + slip >= 1.0:
        raise ValueError("guess and slip must be non-negative and sum to less than 1")
    if response.get("item_difficulty") != "none":
        raise ValueError("baseline simulation has no item difficulty")

    learning = _required(config, "learning", "simulation config")
    _exact_keys(
        learning,
        {"rule", "rate", "correctness_conditioned", "forgetting"},
        "learning",
    )
    if learning.get("rule") != "all_active_opportunity":
        raise ValueError("baseline learning rule must be all_active_opportunity")
    rate = _finite_number(
        _required(learning, "rate", "learning"), "learning.rate"
    )
    if not 0.0 <= rate <= 1.0:
        raise ValueError("learning.rate must be between zero and one")
    if learning.get("correctness_conditioned") is not False:
        raise ValueError("baseline learning must not be correctness-conditioned")
    if learning.get("forgetting") != "none":
        raise ValueError("baseline simulation has no forgetting")

    schedule = _required(config, "schedule", "simulation config")
    _exact_keys(
        schedule,
        {
            "grammar_regimes",
            "acquisition_regime",
            "acquisition",
            "item_order",
            "probe",
        },
        "schedule",
    )
    regimes = _required(schedule, "grammar_regimes", "schedule")
    if (
        not isinstance(regimes, list)
        or not regimes
        or any(not isinstance(value, str) or not value for value in regimes)
        or len(regimes) != len(set(regimes))
    ):
        raise ValueError("schedule.grammar_regimes must contain unique strings")
    if schedule.get("acquisition_regime") not in regimes:
        raise ValueError("schedule.acquisition_regime must be a declared regime")

    acquisition = _required(schedule, "acquisition", "schedule")
    _exact_keys(
        acquisition,
        {
            "mode",
            "exhaustive_coverage_passes",
            "target_opportunities_per_seen_kc",
        },
        "schedule.acquisition",
    )
    if acquisition.get("mode") != "exhaustive_then_q_balanced":
        raise ValueError(
            "baseline acquisition mode must be exhaustive_then_q_balanced"
        )
    coverage_passes = _positive_int(
        _required(
            acquisition,
            "exhaustive_coverage_passes",
            "schedule.acquisition",
        ),
        "schedule.acquisition.exhaustive_coverage_passes",
    )
    if coverage_passes != 1:
        raise ValueError("baseline acquisition must have exactly one coverage pass")
    _positive_int(
        _required(
            acquisition,
            "target_opportunities_per_seen_kc",
            "schedule.acquisition",
        ),
        "schedule.acquisition.target_opportunities_per_seen_kc",
    )
    if schedule.get("item_order") != "keyed_occurrence_rank":
        raise ValueError("baseline item order must be keyed_occurrence_rank")

    probe = _required(schedule, "probe", "schedule")
    _exact_keys(
        probe,
        {"timing", "item_scope", "updates_mastery", "repeats"},
        "schedule.probe",
    )
    if probe.get("timing") != "terminal":
        raise ValueError("baseline probes must be terminal")
    if probe.get("item_scope") != "all_regimes":
        raise ValueError("baseline probes must cover all grammar regimes")
    if probe.get("updates_mastery") is not False:
        raise ValueError("baseline probes must not update mastery")
    _positive_int(_required(probe, "repeats", "probe"), "probe.repeats")

    rng = _required(config, "rng", "simulation config")
    _exact_keys(rng, {"scheme", "rationale"}, "rng")
    if rng.get("scheme") != "keyed_sha256_v1":
        raise ValueError("baseline RNG scheme must be keyed_sha256_v1")

    learner_ids = _required(config, "learner_ids", "simulation config")
    _exact_keys(learner_ids, {"prefix", "zero_pad_width"}, "learner_ids")
    prefix = learner_ids.get("prefix")
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("learner_ids.prefix must be a non-empty string")
    _positive_int(
        _required(learner_ids, "zero_pad_width", "learner_ids"),
        "learner_ids.zero_pad_width",
    )
    if list(config["observable_schema"]) != list(OBSERVABLE_FIELDS):
        raise ValueError("observable_schema differs from the frozen baseline schema")
    if config["oracle_mastery_scope"] != "active_generator_kcs":
        raise ValueError("oracle_mastery_scope must be active_generator_kcs")


def _generator_kc_ids(
    generator_kcs: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[str]:
    if isinstance(generator_kcs, Mapping):
        rows = _required(generator_kcs, "kcs", "generator KC inventory")
    else:
        rows = generator_kcs
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise ValueError("generator K* must contain at least one KC")
    ids = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"generator KC row {index} must be a mapping")
        kc_id = row.get("id")
        if not isinstance(kc_id, str) or not kc_id:
            raise ValueError(f"generator KC row {index} has an invalid id")
        ids.append(kc_id)
    if len(ids) != len(set(ids)):
        raise ValueError("generator K* contains duplicate KC IDs")
    return sorted(ids)


def _validate_inputs(
    items: Sequence[Mapping[str, Any]],
    generator_kcs: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    q_rows: Sequence[Mapping[str, Any]],
    grammar_regime_by_cell: Mapping[str, str],
    config: Mapping[str, Any],
) -> tuple[list[dict[str, str]], list[str], dict[str, tuple[str, ...]]]:
    validate_baseline_config(config)
    if not items:
        raise ValueError("baseline simulation needs a non-empty fixed item bank")

    normalized_items: list[dict[str, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"item row {index} must be a mapping")
        item_id = item.get("item_id")
        cell_id = item.get("cell_id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"item row {index} has an invalid item_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise ValueError(f"item {item_id} has an invalid cell_id")
        normalized_items.append({"item_id": item_id, "cell_id": cell_id})
    item_ids = [row["item_id"] for row in normalized_items]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("fixed item bank contains duplicate item IDs")

    kc_ids = _generator_kc_ids(generator_kcs)
    known_kcs = set(kc_ids)
    active_by_item: dict[str, tuple[str, ...]] = {}
    item_by_id = {row["item_id"]: row for row in normalized_items}
    for index, row in enumerate(q_rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"Q* row {index} must be a mapping")
        item_id = row.get("item_id")
        if item_id not in item_by_id:
            raise ValueError(f"Q* refers to unknown item: {item_id}")
        if item_id in active_by_item:
            raise ValueError(f"Q* contains duplicate rows for item: {item_id}")
        row_cell_id = row.get("cell_id")
        if row_cell_id is not None and row_cell_id != item_by_id[item_id]["cell_id"]:
            raise ValueError(f"Q* cell_id disagrees with item bank for: {item_id}")
        active = row.get("generator_kc_ids")
        if (
            not isinstance(active, Sequence)
            or isinstance(active, (str, bytes))
            or not active
            or any(not isinstance(kc_id, str) or not kc_id for kc_id in active)
        ):
            raise ValueError(f"Q* item {item_id} must activate at least one KC")
        if len(active) != len(set(active)):
            raise ValueError(f"Q* item {item_id} contains duplicate KC edges")
        unknown = set(active) - known_kcs
        if unknown:
            raise ValueError(
                f"Q* item {item_id} activates unknown KCs: {sorted(unknown)}"
            )
        active_by_item[item_id] = tuple(sorted(active))

    missing_q = set(item_ids) - set(active_by_item)
    if missing_q:
        raise ValueError(f"fixed items missing from Q*: {sorted(missing_q)}")
    unsupported_kcs = known_kcs - {
        kc_id for active in active_by_item.values() for kc_id in active
    }
    if unsupported_kcs:
        raise ValueError(f"generator KCs have no item support: {sorted(unsupported_kcs)}")

    allowed_regimes = set(config["schedule"]["grammar_regimes"])
    item_cells = {row["cell_id"] for row in normalized_items}
    missing_regimes = item_cells - set(grammar_regime_by_cell)
    if missing_regimes:
        raise ValueError(
            f"item GrammarCells missing a grammar regime: {sorted(missing_regimes)}"
        )
    invalid_regimes = {
        grammar_regime_by_cell[cell_id]
        for cell_id in item_cells
        if grammar_regime_by_cell[cell_id] not in allowed_regimes
    }
    if invalid_regimes:
        raise ValueError(f"items use undeclared grammar regimes: {sorted(invalid_regimes)}")
    acquisition_regime = config["schedule"]["acquisition_regime"]
    if not any(
        grammar_regime_by_cell[row["cell_id"]] == acquisition_regime
        for row in normalized_items
    ):
        raise ValueError("fixed bank has no item in the acquisition grammar regime")

    return sorted(normalized_items, key=lambda row: row["item_id"]), kc_ids, active_by_item


def _keyed_rng(seed: int, *keys: object) -> np.random.Generator:
    """Return a stable independent stream for one scientifically named draw."""

    payload = json.dumps(
        [seed, *keys], ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    entropy = np.frombuffer(digest, dtype="<u4").tolist()
    return np.random.default_rng(np.random.SeedSequence(entropy))


def _ordered_items(
    items: Sequence[dict[str, str]],
    *,
    seed: int,
    learner_number: int,
    phase: str,
    pass_index: int,
) -> list[dict[str, str]]:
    """Key-rank items so order is independent of input order and RNG history."""

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


def build_acquisition_occurrences(
    seen_items: Sequence[Mapping[str, str]],
    active_by_item: Mapping[str, Sequence[str]],
    *,
    target_opportunities_per_seen_kc: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build one fixed coverage-plus-Q-balanced occurrence multiset.

    Every seen item first receives exactly one occurrence. A deterministic
    greedy top-up then selects additional occurrences until every KC activated
    by seen items reaches the configured opportunity target. The resulting
    multiset depends only on fixed items, Q*, and the target, so all learners
    receive identical item and KC opportunity counts.

    Top-up selection maximizes the number of still-deficient KCs covered,
    prefers the least-exposed item, and finally uses stable item-ID order.
    Learner-specific keyed ordering is a separate operation.
    """

    target = _positive_int(
        target_opportunities_per_seen_kc,
        "target_opportunities_per_seen_kc",
    )
    if not seen_items:
        raise ValueError("acquisition scheduling needs at least one seen item")

    normalized_items: list[dict[str, str]] = []
    for index, item in enumerate(seen_items):
        if not isinstance(item, Mapping):
            raise ValueError(f"seen item row {index} must be a mapping")
        item_id = item.get("item_id")
        cell_id = item.get("cell_id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"seen item row {index} has an invalid item_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise ValueError(f"seen item {item_id} has an invalid cell_id")
        normalized_items.append({"item_id": item_id, "cell_id": cell_id})
    normalized_items.sort(key=lambda row: row["item_id"])
    item_ids = [row["item_id"] for row in normalized_items]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("seen item bank contains duplicate item IDs")

    active_seen_by_item: dict[str, tuple[str, ...]] = {}
    for item_id in item_ids:
        if item_id not in active_by_item:
            raise ValueError(f"seen item is missing from Q*: {item_id}")
        active = active_by_item[item_id]
        if (
            not isinstance(active, Sequence)
            or isinstance(active, (str, bytes))
            or not active
            or any(not isinstance(kc_id, str) or not kc_id for kc_id in active)
        ):
            raise ValueError(f"seen item {item_id} must activate at least one KC")
        active_seen_by_item[item_id] = tuple(sorted(set(active)))

    seen_kc_ids = sorted(
        {
            kc_id
            for active in active_seen_by_item.values()
            for kc_id in active
        }
    )
    if not seen_kc_ids:
        raise ValueError("acquisition scheduling needs at least one seen KC")

    item_exposures = Counter({item_id: 0 for item_id in item_ids})
    kc_opportunities = Counter({kc_id: 0 for kc_id in seen_kc_ids})
    occurrences: list[dict[str, Any]] = []

    def append_item(item: Mapping[str, str], schedule_stage: str) -> None:
        item_id = item["item_id"]
        item_exposures[item_id] += 1
        kc_opportunities.update(active_seen_by_item[item_id])
        occurrences.append(
            {
                "item": dict(item),
                "schedule_stage": schedule_stage,
                # Top-up is not a complete bank pass. Public pass_index has
                # item-local semantics: this item's exposure number.
                "pass_index": item_exposures[item_id],
                "item_exposure_index": item_exposures[item_id],
            }
        )

    # Exactly one exhaustive pass remains mandatory even when it already
    # exceeds a deliberately small KC target.
    for item in normalized_items:
        append_item(item, "exhaustive_coverage")

    maximum_occurrences = len(normalized_items) + target * len(seen_kc_ids)
    while min(kc_opportunities.values()) < target:
        scored: list[tuple[int, int, str, dict[str, str]]] = []
        for item in normalized_items:
            item_id = item["item_id"]
            deficit_reduction = sum(
                kc_opportunities[kc_id] < target
                for kc_id in active_seen_by_item[item_id]
            )
            if deficit_reduction:
                scored.append(
                    (
                        -deficit_reduction,
                        item_exposures[item_id],
                        item_id,
                        item,
                    )
                )
        if not scored:
            raise ValueError("Q-balanced top-up cannot reduce a seen-KC deficit")
        append_item(min(scored)[-1], "q_balanced_top_up")
        if len(occurrences) > maximum_occurrences:
            raise AssertionError("Q-balanced top-up exceeded its deficit bound")

    opportunity_values = list(kc_opportunities.values())
    exposure_values = list(item_exposures.values())
    diagnostics = {
        "schedule_mode": "exhaustive_then_q_balanced",
        "schedule_length": len(occurrences),
        "exhaustive_coverage_occurrences": len(normalized_items),
        "q_balanced_top_up_occurrences": len(occurrences) - len(normalized_items),
        "target_opportunities_per_seen_kc": target,
        "seen_kc_ids": seen_kc_ids,
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
    return occurrences, diagnostics


def order_acquisition_occurrences(
    occurrences: Sequence[Mapping[str, Any]],
    *,
    seed: int,
    learner_number: int,
) -> list[dict[str, Any]]:
    """Key-rank a fixed acquisition occurrence multiset for one learner.

    Occurrences are grouped by item-local exposure index. Thus the exhaustive
    first exposure precedes every top-up and an item's third exposure cannot
    precede its second. Within each exposure layer, unique occurrence tuples
    receive a stable learner-keyed rank.
    """

    normalized: list[dict[str, Any]] = []
    occurrence_keys: set[tuple[str, int]] = set()
    for index, occurrence in enumerate(occurrences):
        if not isinstance(occurrence, Mapping):
            raise ValueError(f"acquisition occurrence {index} must be a mapping")
        item = occurrence.get("item")
        if not isinstance(item, Mapping):
            raise ValueError(f"acquisition occurrence {index} has no item")
        item_id = item.get("item_id")
        cell_id = item.get("cell_id")
        exposure = occurrence.get("item_exposure_index")
        stage = occurrence.get("schedule_stage")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"acquisition occurrence {index} has invalid item_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise ValueError(f"acquisition occurrence {index} has invalid cell_id")
        exposure = _positive_int(
            exposure, f"acquisition occurrence {index} item_exposure_index"
        )
        expected_stage = (
            "exhaustive_coverage" if exposure == 1 else "q_balanced_top_up"
        )
        if stage != expected_stage:
            raise ValueError(
                f"acquisition occurrence {item_id}/{exposure} has invalid stage"
            )
        occurrence_key = (item_id, exposure)
        if occurrence_key in occurrence_keys:
            raise ValueError(f"duplicate acquisition occurrence: {occurrence_key}")
        occurrence_keys.add(occurrence_key)
        normalized.append(
            {
                "item": {"item_id": item_id, "cell_id": cell_id},
                "schedule_stage": stage,
                "pass_index": exposure,
                "item_exposure_index": exposure,
            }
        )

    ordered = sorted(
        normalized,
        key=lambda row: (
            row["item_exposure_index"],
            float(
                _keyed_rng(
                    seed,
                    "item_order",
                    learner_number,
                    "acquisition",
                    row["item_exposure_index"],
                    row["item"]["item_id"],
                ).random()
            ),
            row["item"]["item_id"],
        ),
    )
    return [
        {**row, "schedule_step": schedule_step}
        for schedule_step, row in enumerate(ordered, start=1)
    ]


def simulate_baseline(
    items: Sequence[Mapping[str, Any]],
    generator_kcs: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    q_rows: Sequence[Mapping[str, Any]],
    grammar_regime_by_cell: Mapping[str, str],
    config: Mapping[str, Any],
    *,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Simulate observable interactions and separate private oracle rows.

    Mastery is initialized independently for every learner/KC from the declared
    beta distribution.  Acquisition presents only the configured seen regime.
    For an item requiring multiple KCs, response probability is

    ``guess + (1 - guess - slip) * min(active mastery)``.

    Every active KC receives an opportunity-based update after an acquisition
    response, irrespective of correctness.  Terminal probes cover the complete
    bank and never update mastery.  Oracle mastery mappings contain the active
    generator KCs only; inactive KCs cannot change on an event.
    """

    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if seed != config["seed"]:
        raise ValueError("explicit seed differs from simulation config seed")
    ordered_bank, kc_ids, active_by_item = _validate_inputs(
        items, generator_kcs, q_rows, grammar_regime_by_cell, config
    )

    learner_count = int(config["learners"])
    beta_alpha = float(config["initial_mastery"]["alpha"])
    beta_beta = float(config["initial_mastery"]["beta"])
    guess = float(config["response"]["guess"])
    slip = float(config["response"]["slip"])
    learning_rate = float(config["learning"]["rate"])
    schedule = config["schedule"]
    acquisition_regime = schedule["acquisition_regime"]
    target_opportunities = int(
        schedule["acquisition"]["target_opportunities_per_seen_kc"]
    )
    probe_repeats = int(schedule["probe"]["repeats"])
    prefix = config["learner_ids"]["prefix"]
    zero_pad_width = int(config["learner_ids"]["zero_pad_width"])

    acquisition_items = [
        item
        for item in ordered_bank
        if grammar_regime_by_cell[item["cell_id"]] == acquisition_regime
    ]
    acquisition_occurrences, _schedule_diagnostics = build_acquisition_occurrences(
        acquisition_items,
        active_by_item,
        target_opportunities_per_seen_kc=target_opportunities,
    )
    interactions: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []

    for learner_number in range(1, learner_count + 1):
        learner_id = f"{prefix}{learner_number:0{zero_pad_width}d}"
        mastery = {
            kc_id: float(
                _keyed_rng(
                    seed, "initial_mastery", learner_number, kc_id
                ).beta(beta_alpha, beta_beta)
            )
            for kc_id in kc_ids
        }
        sequence_index = 0

        learner_acquisition = order_acquisition_occurrences(
            acquisition_occurrences,
            seed=seed,
            learner_number=learner_number,
        )
        schedule_rows: list[tuple[str, int, bool, dict[str, str], int]] = [
            (
                "acquisition",
                int(occurrence["pass_index"]),
                True,
                occurrence["item"],
                int(occurrence["item_exposure_index"]),
            )
            for occurrence in learner_acquisition
        ]
        for pass_index in range(1, probe_repeats + 1):
            for item in _ordered_items(
                ordered_bank,
                seed=seed,
                learner_number=learner_number,
                phase="probe",
                pass_index=pass_index,
            ):
                schedule_rows.append(
                    ("probe", pass_index, False, item, pass_index)
                )

        for phase, pass_index, updates_mastery, item, draw_index in schedule_rows:
            sequence_index += 1
            item_id = item["item_id"]
            active_kcs = active_by_item[item_id]
            mastery_before = {kc_id: mastery[kc_id] for kc_id in active_kcs}
            aggregated = min(mastery_before.values())
            probability = guess + (1.0 - guess - slip) * aggregated
            response_keys = (
                (phase, item_id, draw_index)
                if phase == "acquisition"
                else (phase, draw_index, item_id)
            )
            response_draw = float(
                _keyed_rng(
                    seed,
                    "response",
                    learner_number,
                    *response_keys,
                ).random()
            )
            correct = int(response_draw < probability)

            if updates_mastery:
                for kc_id in active_kcs:
                    current = mastery[kc_id]
                    mastery[kc_id] = current + learning_rate * (1.0 - current)
            mastery_after = {kc_id: mastery[kc_id] for kc_id in active_kcs}
            grammar_regime = grammar_regime_by_cell[item["cell_id"]]

            interaction = {
                "learner_id": learner_id,
                "item_id": item_id,
                "sequence_index": sequence_index,
                "correct": correct,
                "phase": phase,
                "pass_index": pass_index,
                "grammar_regime": grammar_regime,
            }
            oracle = {
                "learner_id": learner_id,
                "item_id": item_id,
                "sequence_index": sequence_index,
                "phase": phase,
                "pass_index": pass_index,
                "grammar_regime": grammar_regime,
                "active_generator_kc_ids": list(active_kcs),
                "mastery_before": mastery_before,
                "aggregated_mastery_before": aggregated,
                "response_probability": probability,
                "response_draw": response_draw,
                "correct": correct,
                "updates_mastery": updates_mastery,
                "mastery_after": mastery_after,
            }
            if tuple(interaction) != OBSERVABLE_FIELDS:
                raise AssertionError("internal observable schema drift")
            if tuple(oracle) != ORACLE_FIELDS:
                raise AssertionError("internal oracle schema drift")
            interactions.append(interaction)
            oracle_rows.append(oracle)

    return interactions, oracle_rows
