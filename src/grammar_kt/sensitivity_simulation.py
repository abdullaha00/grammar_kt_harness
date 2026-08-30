"""Downstream simulator-sensitivity worlds over a frozen K*/Q*.

This module is intentionally separate from :mod:`baseline_simulation`.  It
reuses the fixed acquisition scheduling contract, but permits a small declared
set of response and learning perturbations for downstream robustness analysis.
It emits observable rows only: no mastery, response probability, item
difficulty, or learner parameter is exposed to a predictor.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import asdict, dataclass
from statistics import fmean, pstdev
from typing import Any

import numpy as np

from .baseline_simulation import (
    OBSERVABLE_FIELDS,
    build_acquisition_occurrences,
    order_acquisition_occurrences,
    validate_baseline_config,
)


_AGGREGATIONS = {"minimum", "product", "arithmetic_mean"}
_UPDATE_RULES = {"all_opportunities", "correct_only"}


@dataclass(frozen=True)
class SensitivityCondition:
    """One fully declared downstream learner world.

    Optional ranges use independent learner-level ``Beta(2, 2)`` quantiles
    scaled to the inclusive bounds.  A ``None`` range means that the fixed
    scalar value is used for every learner.
    """

    condition_id: str
    aggregation: str = "minimum"
    guess: float = 0.10
    slip: float = 0.10
    learner_guess_slip_range: tuple[float, float] | None = None
    item_difficulty_logit_sd: float = 0.0
    learning_rate: float = 0.02
    learner_learning_rate_range: tuple[float, float] | None = None
    initial_mastery_global_mixture_weight: float = 0.0
    forgetting_per_acquisition_gap: float = 0.0
    update_rule: str = "all_opportunities"

    def __post_init__(self) -> None:
        if not self.condition_id:
            raise ValueError("condition_id must be non-empty")
        if self.aggregation not in _AGGREGATIONS:
            raise ValueError(f"unknown aggregation: {self.aggregation}")
        if self.update_rule not in _UPDATE_RULES:
            raise ValueError(f"unknown update rule: {self.update_rule}")
        for name in ("guess", "slip"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value < 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1)")
        if self.guess + self.slip >= 1.0:
            raise ValueError("guess and slip must sum to less than one")
        if not math.isfinite(self.item_difficulty_logit_sd) or self.item_difficulty_logit_sd < 0:
            raise ValueError("item_difficulty_logit_sd must be finite and non-negative")
        if not math.isfinite(self.learning_rate) or not 0.0 <= self.learning_rate <= 1.0:
            raise ValueError("learning_rate must be finite and in [0, 1]")
        if (
            not math.isfinite(self.initial_mastery_global_mixture_weight)
            or not 0.0 <= self.initial_mastery_global_mixture_weight <= 1.0
        ):
            raise ValueError(
                "initial_mastery_global_mixture_weight must be finite and in [0, 1]"
            )
        if (
            not math.isfinite(self.forgetting_per_acquisition_gap)
            or not 0.0 <= self.forgetting_per_acquisition_gap < 1.0
        ):
            raise ValueError(
                "forgetting_per_acquisition_gap must be finite and in [0, 1)"
            )
        self._validate_range(
            self.learner_guess_slip_range,
            "learner_guess_slip_range",
            upper_exclusive=0.5,
        )
        self._validate_range(
            self.learner_learning_rate_range,
            "learner_learning_rate_range",
            upper_exclusive=None,
        )

    @staticmethod
    def _validate_range(
        value: tuple[float, float] | None,
        context: str,
        *,
        upper_exclusive: float | None,
    ) -> None:
        if value is None:
            return
        if len(value) != 2:
            raise ValueError(f"{context} must have two bounds")
        low, high = (float(bound) for bound in value)
        if not all(math.isfinite(bound) for bound in (low, high)):
            raise ValueError(f"{context} bounds must be finite")
        if not 0.0 <= low < high <= 1.0:
            raise ValueError(f"{context} must satisfy 0 <= low < high <= 1")
        if upper_exclusive is not None and high >= upper_exclusive:
            raise ValueError(f"{context} upper bound must be below {upper_exclusive}")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in (
            "learner_guess_slip_range",
            "learner_learning_rate_range",
        ):
            if value[key] is not None:
                value[key] = list(value[key])
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SensitivityCondition":
        expected = {
            "condition_id",
            "aggregation",
            "guess",
            "slip",
            "learner_guess_slip_range",
            "item_difficulty_logit_sd",
            "learning_rate",
            "learner_learning_rate_range",
            "initial_mastery_global_mixture_weight",
            "forgetting_per_acquisition_gap",
            "update_rule",
        }
        if set(value) != expected:
            raise ValueError(
                "sensitivity condition fields differ: "
                f"missing={sorted(expected - set(value))}, "
                f"unknown={sorted(set(value) - expected)}"
            )
        normalized = dict(value)
        for key in (
            "learner_guess_slip_range",
            "learner_learning_rate_range",
        ):
            if normalized[key] is not None:
                raw = normalized[key]
                if (
                    not isinstance(raw, Sequence)
                    or isinstance(raw, (str, bytes))
                    or len(raw) != 2
                ):
                    raise ValueError(f"{key} must contain two numeric bounds")
                normalized[key] = (float(raw[0]), float(raw[1]))
        return cls(**normalized)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )


def _hash_update(digest: Any, value: Any) -> None:
    digest.update(_canonical_json(value).encode("utf-8"))
    digest.update(b"\n")


def _keyed_rng(seed: int, *keys: object) -> np.random.Generator:
    payload = json.dumps(
        [seed, *keys], ensure_ascii=True, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    entropy = np.frombuffer(digest, dtype="<u4").tolist()
    return np.random.default_rng(np.random.SeedSequence(entropy))


def _scaled_beta_2_2(seed: int, low: float, high: float, *keys: object) -> float:
    quantile = float(_keyed_rng(seed, *keys).beta(2.0, 2.0))
    return low + (high - low) * quantile


def aggregate_mastery(values: Sequence[float], aggregation: str) -> float:
    """Aggregate active-KC mastery under one declared response rule."""

    if not values:
        raise ValueError("response aggregation requires at least one active KC")
    normalized = [float(value) for value in values]
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in normalized):
        raise ValueError("mastery values must be finite and in [0, 1]")
    if aggregation == "minimum":
        return min(normalized)
    if aggregation == "product":
        return math.prod(normalized)
    if aggregation == "arithmetic_mean":
        return fmean(normalized)
    raise ValueError(f"unknown aggregation: {aggregation}")


def response_probability(
    mastery_values: Sequence[float],
    condition: SensitivityCondition,
    *,
    guess: float | None = None,
    slip: float | None = None,
    item_difficulty: float = 0.0,
) -> float:
    """Return the condition probability before the common Bernoulli draw.

    Item difficulty is an offset on the logit of aggregated mastery.  With
    zero difficulty this transformation is the identity, preserving the
    frozen baseline response equation exactly.
    """

    active = aggregate_mastery(mastery_values, condition.aggregation)
    if float(item_difficulty) == 0.0:
        # Preserve the baseline linear response equation bit-for-bit.  The
        # logit offset is needed only in the item-difficulty world.
        latent = active
    else:
        clipped = min(1.0 - 1e-12, max(1e-12, active))
        latent_logit = math.log(clipped / (1.0 - clipped)) - float(item_difficulty)
        if latent_logit >= 0.0:
            latent = 1.0 / (1.0 + math.exp(-latent_logit))
        else:
            exponential = math.exp(latent_logit)
            latent = exponential / (1.0 + exponential)
    effective_guess = condition.guess if guess is None else float(guess)
    effective_slip = condition.slip if slip is None else float(slip)
    if effective_guess < 0.0 or effective_slip < 0.0 or effective_guess + effective_slip >= 1.0:
        raise ValueError("effective guess/slip values are invalid")
    return effective_guess + (1.0 - effective_guess - effective_slip) * latent


def _summary(values: Sequence[float]) -> dict[str, float]:
    return {
        "minimum": min(values),
        "mean": fmean(values),
        "maximum": max(values),
        "population_sd": pstdev(values),
    }


def _normalize_inputs(
    items: Sequence[Mapping[str, Any]],
    generator_kc_ids: Sequence[str],
    true_projection: Mapping[str, Sequence[str]],
    grammar_regime_by_cell: Mapping[str, str],
    design_config: Mapping[str, Any],
) -> tuple[list[dict[str, str]], list[str], dict[str, tuple[str, ...]]]:
    validate_baseline_config(design_config)
    normalized_items: list[dict[str, str]] = []
    for index, row in enumerate(items):
        item_id = row.get("item_id")
        cell_id = row.get("cell_id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"item row {index} has invalid item_id")
        if not isinstance(cell_id, str) or not cell_id:
            raise ValueError(f"item {item_id} has invalid cell_id")
        normalized_items.append({"item_id": item_id, "cell_id": cell_id})
    normalized_items.sort(key=lambda row: row["item_id"])
    item_ids = [row["item_id"] for row in normalized_items]
    if not item_ids or len(item_ids) != len(set(item_ids)):
        raise ValueError("fixed item bank must be non-empty with unique IDs")
    kc_ids = sorted(str(kc_id) for kc_id in generator_kc_ids)
    if not kc_ids or len(kc_ids) != len(set(kc_ids)):
        raise ValueError("generator K* must be non-empty with unique IDs")
    if set(true_projection) != set(item_ids):
        raise ValueError("true Q* must exactly cover the fixed item bank")
    known_kcs = set(kc_ids)
    normalized_projection: dict[str, tuple[str, ...]] = {}
    for item_id in item_ids:
        active = tuple(sorted(str(kc_id) for kc_id in true_projection[item_id]))
        if not active or len(active) != len(set(active)):
            raise ValueError(f"true Q* item {item_id} has invalid active KCs")
        if set(active) - known_kcs:
            raise ValueError(f"true Q* item {item_id} has unknown active KCs")
        normalized_projection[item_id] = active
    supported = {kc_id for active in normalized_projection.values() for kc_id in active}
    if supported != known_kcs:
        raise ValueError("true Q* must support every generator KC")
    cells = {row["cell_id"] for row in normalized_items}
    if cells - set(grammar_regime_by_cell):
        raise ValueError("fixed item bank has missing grammar regimes")
    allowed = set(design_config["schedule"]["grammar_regimes"])
    if {grammar_regime_by_cell[cell_id] for cell_id in cells} - allowed:
        raise ValueError("fixed item bank uses an undeclared grammar regime")
    return normalized_items, kc_ids, normalized_projection


def _probe_order(
    items: Sequence[dict[str, str]],
    *,
    seed: int,
    learner_number: int,
    repeat: int,
) -> list[dict[str, str]]:
    return sorted(
        items,
        key=lambda item: (
            float(
                _keyed_rng(
                    seed,
                    "item_order",
                    learner_number,
                    "probe",
                    repeat,
                    item["item_id"],
                ).random()
            ),
            item["item_id"],
        ),
    )


def simulate_sensitivity(
    items: Sequence[Mapping[str, Any]],
    generator_kc_ids: Sequence[str],
    true_projection: Mapping[str, Sequence[str]],
    grammar_regime_by_cell: Mapping[str, str],
    design_config: Mapping[str, Any],
    condition: SensitivityCondition,
    *,
    acquisition_item_ids: Collection[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Simulate one downstream world and return observable events plus audit.

    ``acquisition_item_ids`` is an outcome-free design hook for later
    generalisation studies.  It may select only fixed items already assigned to
    the declared acquisition regime.  The terminal probe always retains the
    complete fixed bank.  This robustness study leaves the hook as ``None``.
    """

    ordered_bank, kc_ids, active_by_item = _normalize_inputs(
        items,
        generator_kc_ids,
        true_projection,
        grammar_regime_by_cell,
        design_config,
    )
    seed = int(design_config["seed"])
    learners = int(design_config["learners"])
    beta_alpha = float(design_config["initial_mastery"]["alpha"])
    beta_beta = float(design_config["initial_mastery"]["beta"])
    acquisition_regime = str(design_config["schedule"]["acquisition_regime"])
    target = int(
        design_config["schedule"]["acquisition"][
            "target_opportunities_per_seen_kc"
        ]
    )
    repeats = int(design_config["schedule"]["probe"]["repeats"])
    prefix = str(design_config["learner_ids"]["prefix"])
    zero_pad = int(design_config["learner_ids"]["zero_pad_width"])

    eligible_ids = {
        item["item_id"]
        for item in ordered_bank
        if grammar_regime_by_cell[item["cell_id"]] == acquisition_regime
    }
    if acquisition_item_ids is None:
        selected_ids = eligible_ids
    else:
        selected_ids = {str(item_id) for item_id in acquisition_item_ids}
        if not selected_ids:
            raise ValueError("acquisition_item_ids must not be empty")
        unknown = selected_ids - {item["item_id"] for item in ordered_bank}
        if unknown:
            raise ValueError(f"acquisition_item_ids contains unknown IDs: {sorted(unknown)}")
        outside = selected_ids - eligible_ids
        if outside:
            raise ValueError(
                "acquisition_item_ids must stay within the declared acquisition "
                f"regime: {sorted(outside)}"
            )
    acquisition_items = [
        item for item in ordered_bank if item["item_id"] in selected_ids
    ]
    occurrences, schedule_diagnostics = build_acquisition_occurrences(
        acquisition_items,
        active_by_item,
        target_opportunities_per_seen_kc=target,
    )

    item_difficulty_z = {
        item["item_id"]: float(
            _keyed_rng(seed, "item_difficulty_z", item["item_id"]).normal()
        )
        for item in ordered_bank
    }
    item_difficulties = {
        item_id: condition.item_difficulty_logit_sd * value
        for item_id, value in item_difficulty_z.items()
    }
    item_latent_digest = hashlib.sha256()
    for item_id, value in sorted(item_difficulty_z.items()):
        _hash_update(item_latent_digest, [item_id, value.hex()])

    initial_latent_digest = hashlib.sha256()
    realized_initial_digest = hashlib.sha256()
    learner_latent_digest = hashlib.sha256()
    event_key_digest = hashlib.sha256()
    response_uniform_digest = hashlib.sha256()
    outcome_digest = hashlib.sha256()
    learner_guesses: list[float] = []
    learner_slips: list[float] = []
    learner_rates: list[float] = []
    realized_initial_by_kc: dict[str, list[float]] = {
        kc_id: [] for kc_id in kc_ids
    }
    global_initial_selections = 0
    events: list[dict[str, Any]] = []

    for learner_number in range(1, learners + 1):
        learner_id = f"{prefix}{learner_number:0{zero_pad}d}"
        global_initial = float(
            _keyed_rng(
                seed, "initial_mastery_global", learner_number
            ).beta(beta_alpha, beta_beta)
        )
        mastery: dict[str, float] = {}
        for kc_id in kc_ids:
            independent_initial = float(
                _keyed_rng(
                    seed, "initial_mastery", learner_number, kc_id
                ).beta(beta_alpha, beta_beta)
            )
            mixture_selector = float(
                _keyed_rng(
                    seed,
                    "initial_mastery_global_mixture_selector",
                    learner_number,
                    kc_id,
                ).random()
            )
            _hash_update(
                initial_latent_digest,
                [
                    learner_number,
                    kc_id,
                    independent_initial.hex(),
                    global_initial.hex(),
                    mixture_selector.hex(),
                ],
            )
            selected_global = (
                mixture_selector
                < condition.initial_mastery_global_mixture_weight
            )
            mastery[kc_id] = global_initial if selected_global else independent_initial
            global_initial_selections += int(selected_global)
            realized_initial_by_kc[kc_id].append(mastery[kc_id])
            _hash_update(
                realized_initial_digest,
                [learner_number, kc_id, mastery[kc_id].hex()],
            )

        guess_latent = float(
            _keyed_rng(seed, "learner_guess_beta_2_2", learner_number).beta(2.0, 2.0)
        )
        slip_latent = float(
            _keyed_rng(seed, "learner_slip_beta_2_2", learner_number).beta(2.0, 2.0)
        )
        rate_latent = float(
            _keyed_rng(seed, "learner_rate_beta_2_2", learner_number).beta(2.0, 2.0)
        )
        _hash_update(
            learner_latent_digest,
            [
                learner_number,
                guess_latent.hex(),
                slip_latent.hex(),
                rate_latent.hex(),
            ],
        )
        if condition.learner_guess_slip_range is None:
            learner_guess = condition.guess
            learner_slip = condition.slip
        else:
            low, high = condition.learner_guess_slip_range
            learner_guess = low + (high - low) * guess_latent
            learner_slip = low + (high - low) * slip_latent
        if condition.learner_learning_rate_range is None:
            learner_rate = condition.learning_rate
        else:
            low, high = condition.learner_learning_rate_range
            learner_rate = low + (high - low) * rate_latent
        learner_guesses.append(learner_guess)
        learner_slips.append(learner_slip)
        learner_rates.append(learner_rate)

        learner_acquisition = order_acquisition_occurrences(
            occurrences,
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
        for repeat in range(1, repeats + 1):
            schedule_rows.extend(
                ("probe", repeat, False, item, repeat)
                for item in _probe_order(
                    ordered_bank,
                    seed=seed,
                    learner_number=learner_number,
                    repeat=repeat,
                )
            )

        acquisition_index = 0
        for sequence_index, (
            phase,
            pass_index,
            updates_mastery,
            item,
            draw_index,
        ) in enumerate(schedule_rows, start=1):
            item_id = item["item_id"]
            active_kcs = active_by_item[item_id]
            if phase == "acquisition":
                if acquisition_index and condition.forgetting_per_acquisition_gap:
                    retention = 1.0 - condition.forgetting_per_acquisition_gap
                    for kc_id in kc_ids:
                        mastery[kc_id] *= retention
                acquisition_index += 1
            probability = response_probability(
                [mastery[kc_id] for kc_id in active_kcs],
                condition,
                guess=learner_guess,
                slip=learner_slip,
                item_difficulty=item_difficulties[item_id],
            )
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
            if updates_mastery and (
                condition.update_rule == "all_opportunities" or correct == 1
            ):
                for kc_id in active_kcs:
                    current = mastery[kc_id]
                    mastery[kc_id] = current + learner_rate * (1.0 - current)

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
            if tuple(interaction) != OBSERVABLE_FIELDS:
                raise AssertionError("internal observable schema drift")
            events.append(interaction)
            event_key = [
                learner_number,
                sequence_index,
                phase,
                item_id,
                pass_index,
                grammar_regime,
            ]
            _hash_update(event_key_digest, event_key)
            _hash_update(
                response_uniform_digest,
                [*event_key, response_draw.hex()],
            )
            _hash_update(outcome_digest, [*event_key, correct])

    initial_matrix = np.asarray(
        [realized_initial_by_kc[kc_id] for kc_id in kc_ids], dtype=float
    )
    if len(kc_ids) > 1 and learners > 1:
        correlation = np.corrcoef(initial_matrix)
        off_diagonal = correlation[~np.eye(len(kc_ids), dtype=bool)]
        mean_pairwise_correlation = float(np.nanmean(off_diagonal))
    else:
        mean_pairwise_correlation = 0.0
    audit = {
        "condition_id": condition.condition_id,
        "seed": seed,
        "learners": learners,
        "events": len(events),
        "acquisition_events": sum(row["phase"] == "acquisition" for row in events),
        "probe_events": sum(row["phase"] == "probe" for row in events),
        "acquisition_item_ids_hook": (
            None if acquisition_item_ids is None else sorted(selected_ids)
        ),
        "acquisition_schedule": schedule_diagnostics,
        "common_random_number_hashes": {
            "initial_mastery_latents_sha256": initial_latent_digest.hexdigest(),
            "learner_heterogeneity_latents_sha256": learner_latent_digest.hexdigest(),
            "item_difficulty_latents_sha256": item_latent_digest.hexdigest(),
            "event_keys_sha256": event_key_digest.hexdigest(),
            "response_uniforms_sha256": response_uniform_digest.hexdigest(),
        },
        "realized_initial_mastery_sha256": realized_initial_digest.hexdigest(),
        "realized_initial_mastery_summary": {
            "marginal": _summary(initial_matrix.ravel().tolist()),
            "mean_pairwise_kc_correlation": mean_pairwise_correlation,
            "declared_global_mixture_weight": condition.initial_mastery_global_mixture_weight,
            "realized_global_selection_fraction": global_initial_selections
            / (learners * len(kc_ids)),
            "directed_prerequisite_learning": False,
        },
        "outcome_sha256": outcome_digest.hexdigest(),
        "realized_parameter_summary": {
            "learner_guess": _summary(learner_guesses),
            "learner_slip": _summary(learner_slips),
            "learner_learning_rate": _summary(learner_rates),
            "item_difficulty": _summary(list(item_difficulties.values())),
        },
        "observable_fields": list(OBSERVABLE_FIELDS),
        "private_event_state_emitted": False,
    }
    return events, audit
