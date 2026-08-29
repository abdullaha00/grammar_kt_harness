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
from collections.abc import Mapping, Sequence
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

    _positive_int(_required(config, "learners", "simulation config"), "learners")

    initial = _required(config, "initial_mastery", "simulation config")
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
    _positive_int(
        _required(schedule, "acquisition_passes", "schedule"),
        "schedule.acquisition_passes",
    )
    if schedule.get("item_order") != "keyed_rank":
        raise ValueError("baseline item order must be keyed_rank")

    probe = _required(schedule, "probe", "schedule")
    if probe.get("timing") != "terminal":
        raise ValueError("baseline probes must be terminal")
    if probe.get("item_scope") != "all_regimes":
        raise ValueError("baseline probes must cover all grammar regimes")
    if probe.get("updates_mastery") is not False:
        raise ValueError("baseline probes must not update mastery")
    _positive_int(_required(probe, "repeats", "probe"), "probe.repeats")

    rng = _required(config, "rng", "simulation config")
    if rng.get("scheme") != "keyed_sha256_v1":
        raise ValueError("baseline RNG scheme must be keyed_sha256_v1")

    learner_ids = _required(config, "learner_ids", "simulation config")
    prefix = learner_ids.get("prefix")
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("learner_ids.prefix must be a non-empty string")
    _positive_int(
        _required(learner_ids, "zero_pad_width", "learner_ids"),
        "learner_ids.zero_pad_width",
    )


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
    acquisition_passes = int(schedule["acquisition_passes"])
    probe_repeats = int(schedule["probe"]["repeats"])
    prefix = config["learner_ids"]["prefix"]
    zero_pad_width = int(config["learner_ids"]["zero_pad_width"])

    acquisition_items = [
        item
        for item in ordered_bank
        if grammar_regime_by_cell[item["cell_id"]] == acquisition_regime
    ]
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

        schedule_rows: list[tuple[str, int, bool, Sequence[dict[str, str]]]] = [
            ("acquisition", pass_index, True, acquisition_items)
            for pass_index in range(1, acquisition_passes + 1)
        ]
        schedule_rows.extend(
            ("probe", pass_index, False, ordered_bank)
            for pass_index in range(1, probe_repeats + 1)
        )

        for phase, pass_index, updates_mastery, phase_items in schedule_rows:
            for item in _ordered_items(
                phase_items,
                seed=seed,
                learner_number=learner_number,
                phase=phase,
                pass_index=pass_index,
            ):
                sequence_index += 1
                item_id = item["item_id"]
                active_kcs = active_by_item[item_id]
                mastery_before = {kc_id: mastery[kc_id] for kc_id in active_kcs}
                aggregated = min(mastery_before.values())
                probability = guess + (1.0 - guess - slip) * aggregated
                response_draw = float(
                    _keyed_rng(
                        seed,
                        "response",
                        learner_number,
                        phase,
                        pass_index,
                        item_id,
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
