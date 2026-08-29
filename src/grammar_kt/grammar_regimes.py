"""Deterministic grammar-regime design from fixed structural evidence only.

The regime designer consumes canonical GrammarCells and, optionally, the fixed
generator-KC inventory and item-to-cell identities.  It has no learner-event
input.  Selection is made over feature tuples rather than GrammarCell IDs so a
change in source identifiers cannot change the scientific partition.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

from .kc import activation_matches


REGIMES = ("seen", "unseen_combination", "unseen_value")
_OBSERVATION_FIELDS = {
    "correct",
    "learner_id",
    "mastery_after",
    "mastery_before",
    "outcome",
    "response_probability",
    "sequence_index",
}


class GrammarRegimeDesignError(ValueError):
    """Raised when declared regime constraints cannot be satisfied."""


def recommended_regime_design() -> dict[str, Any]:
    """Return the preregisterable full-v1 structural search defaults.

    The numbers describe desired measurement cohort sizes, not English feature
    names.  The same machinery can therefore be used with another declared
    grammar schema by changing only its cells and, if needed, these sizes.
    """

    return {
        "design_id": "grammar_regimes_structural_v1",
        "semantic_tie_seed": 20260829,
        "unseen_value": {
            "target_cells": 6,
            "minimum_cells": 4,
            "maximum_cells": 8,
            "maximum_trigger_values": 1,
            "maximum_unseen_value_only_kcs": 0,
            "minimum_remaining_cells_per_kc": 1,
        },
        "unseen_combination": {
            "target_cells": 15,
            "minimum_cells": 12,
            "beam_width": 512,
            "minimum_seen_cells_per_value": 1,
            "minimum_seen_cells_per_pair": 1,
            "minimum_seen_cells_per_kc": 1,
            "require_pairwise_seen": True,
        },
        "items": {"minimum_items_per_holdout_cell": 1},
    }


def _semantic_hash(value: Any, seed: int) -> str:
    payload = json.dumps(
        [seed, value], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _feature_tuple(cell: Mapping[str, Any], dimensions: Sequence[str]) -> tuple[str, ...]:
    return tuple(str(cell["features"][dimension]) for dimension in dimensions)


def _feature_values(
    features: Mapping[str, str], dimensions: Sequence[str]
) -> tuple[tuple[str, str], ...]:
    return tuple((dimension, str(features[dimension])) for dimension in dimensions)


def _feature_pairs(
    features: Mapping[str, str], dimensions: Sequence[str]
) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (left, str(features[left]), right, str(features[right]))
        for left, right in itertools.combinations(dimensions, 2)
    )


def _normalize_inputs(
    schema: Mapping[str, Any],
    cells: Sequence[Mapping[str, Any]],
    generator_kcs: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
    items: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    dimensions = tuple(schema["dimension_order"])
    if not dimensions or len(set(dimensions)) != len(dimensions):
        raise GrammarRegimeDesignError("schema dimension_order must be non-empty and unique")
    if not cells:
        raise GrammarRegimeDesignError("grammar-regime design needs canonical cells")

    cell_ids: set[str] = set()
    tuples: set[tuple[str, ...]] = set()
    normalized_cells = []
    expected = set(dimensions)
    for raw in cells:
        forbidden = _OBSERVATION_FIELDS & set(raw)
        if forbidden:
            raise GrammarRegimeDesignError(
                f"GrammarCell input contains learner-observation fields: {sorted(forbidden)}"
            )
        cell_id = str(raw["cell_id"])
        if not cell_id or cell_id in cell_ids:
            raise GrammarRegimeDesignError("GrammarCell IDs must be non-empty and unique")
        features = {str(key): str(value) for key, value in raw["features"].items()}
        if set(features) != expected:
            raise GrammarRegimeDesignError(f"wrong GrammarCell dimensions: {cell_id}")
        for dimension in dimensions:
            allowed = schema.get("dimensions", {}).get(dimension, {}).get("allowed_values")
            if allowed is not None and features[dimension] not in {str(value) for value in allowed}:
                raise GrammarRegimeDesignError(
                    f"invalid GrammarCell value: {dimension}={features[dimension]}"
                )
        semantic_tuple = tuple(features[dimension] for dimension in dimensions)
        if semantic_tuple in tuples:
            raise GrammarRegimeDesignError("GrammarCells must have unique feature tuples")
        cell_ids.add(cell_id)
        tuples.add(semantic_tuple)
        normalized_cells.append({"cell_id": cell_id, "features": features})
    normalized_cells.sort(key=lambda row: _feature_tuple(row, dimensions))

    if generator_kcs is None:
        kcs: list[dict[str, Any]] = []
    elif isinstance(generator_kcs, Mapping):
        kcs = [dict(row) for row in generator_kcs.get("kcs", [])]
    else:
        kcs = [dict(row) for row in generator_kcs]
    kc_ids = [str(row["id"]) for row in kcs]
    if len(kc_ids) != len(set(kc_ids)):
        raise GrammarRegimeDesignError("generator-KC IDs must be unique")
    for row in kcs:
        forbidden = _OBSERVATION_FIELDS & set(row)
        if forbidden:
            raise GrammarRegimeDesignError(
                f"generator-KC input contains learner-observation fields: {sorted(forbidden)}"
            )
        if "activation_rule" not in row:
            raise GrammarRegimeDesignError(f"generator KC lacks activation_rule: {row['id']}")

    item_count: Counter[str] | None = None
    if items is not None:
        item_count = Counter()
        item_ids: set[str] = set()
        for row in items:
            forbidden = _OBSERVATION_FIELDS & set(row)
            if forbidden:
                raise GrammarRegimeDesignError(
                    f"item input contains learner-observation fields: {sorted(forbidden)}"
                )
            item_id = str(row["item_id"])
            cell_id = str(row["cell_id"])
            if not item_id or item_id in item_ids:
                raise GrammarRegimeDesignError("item IDs must be non-empty and unique")
            if cell_id not in cell_ids:
                raise GrammarRegimeDesignError(f"item refers to unknown GrammarCell: {item_id}")
            item_ids.add(item_id)
            item_count[cell_id] += 1

    active_by_index: list[frozenset[str]] = []
    for cell in normalized_cells:
        active_by_index.append(
            frozenset(
                str(kc["id"])
                for kc in kcs
                if activation_matches(cell["features"], kc["activation_rule"])
            )
        )
    return {
        "dimensions": dimensions,
        "cells": normalized_cells,
        "kcs": kcs,
        "active_by_index": active_by_index,
        "item_count": item_count,
    }


def _validate_design(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    design = recommended_regime_design() if raw is None else json.loads(json.dumps(raw))
    required = {
        "design_id",
        "semantic_tie_seed",
        "unseen_value",
        "unseen_combination",
        "items",
    }
    if set(design) != required:
        raise GrammarRegimeDesignError(
            f"regime design keys must be exactly {sorted(required)}"
        )
    unseen_value = design["unseen_value"]
    combination = design["unseen_combination"]
    item_design = design["items"]
    required_novel = {
        "target_cells",
        "minimum_cells",
        "maximum_cells",
        "maximum_trigger_values",
        "maximum_unseen_value_only_kcs",
        "minimum_remaining_cells_per_kc",
    }
    required_combination = {
        "target_cells",
        "minimum_cells",
        "beam_width",
        "minimum_seen_cells_per_value",
        "minimum_seen_cells_per_pair",
        "minimum_seen_cells_per_kc",
        "require_pairwise_seen",
    }
    if not required_novel <= set(unseen_value):
        raise GrammarRegimeDesignError("unseen_value design is incomplete")
    if not required_combination <= set(combination):
        raise GrammarRegimeDesignError("unseen_combination design is incomplete")
    integers = [
        unseen_value[key]
        for key in required_novel
        if key != "maximum_unseen_value_only_kcs"
    ] + [
        unseen_value["maximum_unseen_value_only_kcs"],
        combination["target_cells"],
        combination["minimum_cells"],
        combination["beam_width"],
        combination["minimum_seen_cells_per_value"],
        combination["minimum_seen_cells_per_pair"],
        combination["minimum_seen_cells_per_kc"],
        item_design["minimum_items_per_holdout_cell"],
    ]
    if any(int(value) != value or int(value) < 0 for value in integers):
        raise GrammarRegimeDesignError("regime design counts must be non-negative integers")
    if (
        int(unseen_value["minimum_cells"]) < 1
        or int(combination["minimum_cells"]) < 1
        or int(combination["minimum_seen_cells_per_value"]) < 1
        or int(item_design["minimum_items_per_holdout_cell"]) < 1
    ):
        raise GrammarRegimeDesignError(
            "regime cohort and constituent-support minima must be positive"
        )
    if not (
        int(unseen_value["minimum_cells"])
        <= int(unseen_value["target_cells"])
        <= int(unseen_value["maximum_cells"])
    ):
        raise GrammarRegimeDesignError("unseen-value minimum/target/maximum are inconsistent")
    if int(unseen_value["maximum_trigger_values"]) < 1:
        raise GrammarRegimeDesignError("maximum_trigger_values must be positive")
    if int(combination["minimum_cells"]) > int(combination["target_cells"]):
        raise GrammarRegimeDesignError("combination minimum cannot exceed target")
    if int(combination["beam_width"]) < 1:
        raise GrammarRegimeDesignError("beam_width must be positive")
    return design


def _kc_support(
    indices: Iterable[int], active_by_index: Sequence[frozenset[str]], kc_ids: Sequence[str]
) -> Counter[str]:
    support: Counter[str] = Counter({kc_id: 0 for kc_id in kc_ids})
    for index in indices:
        support.update(active_by_index[index])
    return support


def _choose_unseen_value(
    normalized: Mapping[str, Any], design: Mapping[str, Any]
) -> dict[str, Any]:
    dimensions = normalized["dimensions"]
    cells = normalized["cells"]
    active = normalized["active_by_index"]
    item_count = normalized["item_count"]
    kc_ids = [str(row["id"]) for row in normalized["kcs"]]
    config = design["unseen_value"]
    minimum_items = int(design["items"]["minimum_items_per_holdout_cell"])
    all_observed_values = sorted(
        {
            pair
            for cell in cells
            for pair in _feature_values(cell["features"], dimensions)
        }
    )
    observed_values = list(all_observed_values)
    declared_candidates = config.get("candidate_values")
    if declared_candidates is not None:
        allowed = {
            (str(dimension), str(value))
            for dimension, values in declared_candidates.items()
            for value in values
        }
        unknown = allowed - set(all_observed_values)
        if unknown:
            raise GrammarRegimeDesignError(
                f"declared unseen-value candidates are unobserved: {sorted(unknown)}"
            )
        observed_values = sorted(allowed)

    all_indices = set(range(len(cells)))
    total_kc_support = _kc_support(all_indices, active, kc_ids)
    feasible = []
    evaluated = 0
    max_triggers = int(config["maximum_trigger_values"])
    for trigger_count in range(1, max_triggers + 1):
        for triggers in itertools.combinations(observed_values, trigger_count):
            evaluated += 1
            trigger_dimensions = [dimension for dimension, _value in triggers]
            if len(set(trigger_dimensions)) != len(trigger_dimensions):
                continue
            novel = {
                index
                for index, cell in enumerate(cells)
                if any(cell["features"][dimension] == value for dimension, value in triggers)
            }
            count = len(novel)
            if not int(config["minimum_cells"]) <= count <= int(config["maximum_cells"]):
                continue
            if item_count is not None and any(
                item_count[cells[index]["cell_id"]] < minimum_items for index in novel
            ):
                continue
            remaining = all_indices - novel
            if not remaining:
                continue
            remaining_values = {
                pair
                for index in remaining
                for pair in _feature_values(cells[index]["features"], dimensions)
            }
            derived_unseen = set(all_observed_values) - remaining_values
            remaining_kc = _kc_support(remaining, active, kc_ids)
            unseen_only_kcs = sorted(
                kc_id
                for kc_id in kc_ids
                if total_kc_support[kc_id] > 0 and remaining_kc[kc_id] == 0
            )
            if len(unseen_only_kcs) > int(config["maximum_unseen_value_only_kcs"]):
                continue
            if any(
                0 < remaining_kc[kc_id] < int(config["minimum_remaining_cells_per_kc"])
                for kc_id in kc_ids
            ):
                continue
            trigger_payload = [list(pair) for pair in triggers]
            score = (
                len(unseen_only_kcs),
                abs(count - int(config["target_cells"])),
                len(derived_unseen - set(triggers)),
                _semantic_hash(trigger_payload, int(design["semantic_tie_seed"])),
            )
            feasible.append(
                {
                    "score": score,
                    "indices": frozenset(novel),
                    "triggers": tuple(triggers),
                    "derived_unseen": tuple(sorted(derived_unseen)),
                    "unseen_only_kcs": tuple(unseen_only_kcs),
                }
            )
    if not feasible:
        raise GrammarRegimeDesignError(
            "no unseen-value cohort satisfies the declared size, item, and KC constraints"
        )
    selected = min(feasible, key=lambda row: row["score"])
    return {**selected, "evaluated_candidates": evaluated, "feasible_candidates": len(feasible)}


def _counter_after_removal(
    cells: Sequence[Mapping[str, Any]],
    dimensions: Sequence[str],
    base_indices: set[int],
    removed: frozenset[int],
) -> tuple[Counter[tuple[str, str]], Counter[tuple[str, str, str, str]]]:
    values: Counter[tuple[str, str]] = Counter()
    pairs: Counter[tuple[str, str, str, str]] = Counter()
    for index in base_indices - set(removed):
        values.update(_feature_values(cells[index]["features"], dimensions))
        pairs.update(_feature_pairs(cells[index]["features"], dimensions))
    return values, pairs


def _state_valid(
    selected: frozenset[int],
    base_indices: set[int],
    normalized: Mapping[str, Any],
    design: Mapping[str, Any],
    base_value_support: Counter[tuple[str, str]],
    base_pair_support: Counter[tuple[str, str, str, str]],
    base_kc_support: Counter[str],
) -> bool:
    dimensions = normalized["dimensions"]
    cells = normalized["cells"]
    active = normalized["active_by_index"]
    kc_ids = [str(row["id"]) for row in normalized["kcs"]]
    config = design["unseen_combination"]
    values = base_value_support.copy()
    pairs = base_pair_support.copy()
    support = base_kc_support.copy()
    for index in selected:
        values.subtract(_feature_values(cells[index]["features"], dimensions))
        pairs.subtract(_feature_pairs(cells[index]["features"], dimensions))
        support.subtract(active[index])
    required_values = {
        pair
        for index in selected
        for pair in _feature_values(cells[index]["features"], dimensions)
    }
    if any(
        values[pair] < int(config["minimum_seen_cells_per_value"])
        for pair in required_values
    ):
        return False
    if bool(config["require_pairwise_seen"]):
        required_pairs = {
            pair
            for index in selected
            for pair in _feature_pairs(cells[index]["features"], dimensions)
        }
        if any(
            pairs[pair] < int(config["minimum_seen_cells_per_pair"])
            for pair in required_pairs
        ):
            return False
    if any(
        base_kc_support[kc_id] > 0
        and support[kc_id] < int(config["minimum_seen_cells_per_kc"])
        for kc_id in kc_ids
    ):
        return False
    return True


def _state_score(
    selected: frozenset[int],
    base_indices: set[int],
    normalized: Mapping[str, Any],
    design: Mapping[str, Any],
    base_value_support: Counter[tuple[str, str]],
    base_pair_support: Counter[tuple[str, str, str, str]],
) -> tuple[Any, ...]:
    dimensions = normalized["dimensions"]
    cells = normalized["cells"]
    active = normalized["active_by_index"]
    values = base_value_support.copy()
    pairs = base_pair_support.copy()
    for index in selected:
        values.subtract(_feature_values(cells[index]["features"], dimensions))
        pairs.subtract(_feature_pairs(cells[index]["features"], dimensions))
    required_pairs = {
        pair
        for index in selected
        for pair in _feature_pairs(cells[index]["features"], dimensions)
    }
    pairwise_cells = sum(
        all(pairs[pair] > 0 for pair in _feature_pairs(cells[index]["features"], dimensions))
        for index in selected
    )
    distinct_values = len(
        {
            pair
            for index in selected
            for pair in _feature_values(cells[index]["features"], dimensions)
        }
    )
    distinct_kc_rows = len({active[index] for index in selected})
    minimum_pair_margin = min((pairs[pair] for pair in required_pairs), default=0)
    minimum_value_margin = min(
        (
            values[pair]
            for index in selected
            for pair in _feature_values(cells[index]["features"], dimensions)
        ),
        default=0,
    )
    semantic_rows = [list(_feature_tuple(cells[index], dimensions)) for index in sorted(selected)]
    return (
        -pairwise_cells,
        -distinct_kc_rows,
        -distinct_values,
        -minimum_pair_margin,
        -minimum_value_margin,
        _semantic_hash(semantic_rows, int(design["semantic_tie_seed"])),
    )


def _choose_unseen_combinations(
    normalized: Mapping[str, Any],
    design: Mapping[str, Any],
    unseen_value_indices: frozenset[int],
) -> dict[str, Any]:
    cells = normalized["cells"]
    dimensions = normalized["dimensions"]
    item_count = normalized["item_count"]
    config = design["unseen_combination"]
    minimum_items = int(design["items"]["minimum_items_per_holdout_cell"])
    base_indices = set(range(len(cells))) - set(unseen_value_indices)
    candidates = [
        index
        for index in sorted(
            base_indices,
            key=lambda idx: (
                _semantic_hash(
                    list(_feature_tuple(cells[idx], dimensions)),
                    int(design["semantic_tie_seed"]),
                ),
                _feature_tuple(cells[idx], dimensions),
            ),
        )
        if item_count is None or item_count[cells[index]["cell_id"]] >= minimum_items
    ]
    target = int(config["target_cells"])
    beam_width = int(config["beam_width"])
    base_value_support, base_pair_support = _counter_after_removal(
        cells, dimensions, base_indices, frozenset()
    )
    kc_ids = [str(row["id"]) for row in normalized["kcs"]]
    base_kc_support = _kc_support(
        base_indices, normalized["active_by_index"], kc_ids
    )
    beam: list[tuple[int, ...]] = [tuple()]
    deepest: list[tuple[int, ...]] = [tuple()]
    evaluated_states = 0
    for _depth in range(1, target + 1):
        expanded: set[tuple[int, ...]] = set()
        for positions in beam:
            start = positions[-1] + 1 if positions else 0
            for position in range(start, len(candidates)):
                proposal = positions + (position,)
                selected = frozenset(candidates[pos] for pos in proposal)
                evaluated_states += 1
                if _state_valid(
                    selected,
                    base_indices,
                    normalized,
                    design,
                    base_value_support,
                    base_pair_support,
                    base_kc_support,
                ):
                    expanded.add(proposal)
        if not expanded:
            break
        scored = sorted(
            expanded,
            key=lambda positions: _state_score(
                frozenset(candidates[pos] for pos in positions),
                base_indices,
                normalized,
                design,
                base_value_support,
                base_pair_support,
            ),
        )
        beam = scored[:beam_width]
        deepest = beam
    best_positions = min(
        deepest,
        key=lambda positions: _state_score(
            frozenset(candidates[pos] for pos in positions),
            base_indices,
            normalized,
            design,
            base_value_support,
            base_pair_support,
        ),
    )
    selected = frozenset(candidates[position] for position in best_positions)
    if len(selected) < int(config["minimum_cells"]):
        raise GrammarRegimeDesignError(
            "no unseen-combination cohort satisfies the declared semantic constraints "
            f"(achieved {len(selected)}, required {int(config['minimum_cells'])})"
        )
    return {
        "indices": selected,
        "candidate_cells": len(candidates),
        "evaluated_states": evaluated_states,
        "target_reached": len(selected) == target,
    }


def _supports_by_regime(
    normalized: Mapping[str, Any], regime_by_index: Mapping[int, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dimensions = normalized["dimensions"]
    cells = normalized["cells"]
    value_support: Counter[tuple[str, str, str]] = Counter()
    pair_support: Counter[tuple[str, str, str, str, str]] = Counter()
    for index, cell in enumerate(cells):
        regime = regime_by_index[index]
        for dimension, value in _feature_values(cell["features"], dimensions):
            value_support[(dimension, value, regime)] += 1
        for left, left_value, right, right_value in _feature_pairs(cell["features"], dimensions):
            pair_support[(left, left_value, right, right_value, regime)] += 1
    observed_values = sorted({key[:2] for key in value_support})
    observed_pairs = sorted({key[:4] for key in pair_support})
    value_rows = [
        {
            "dimension": dimension,
            "value": value,
            "total_cells": sum(value_support[(dimension, value, regime)] for regime in REGIMES),
            **{
                f"{regime}_cells": value_support[(dimension, value, regime)]
                for regime in REGIMES
            },
        }
        for dimension, value in observed_values
    ]
    pair_rows = [
        {
            "left_dimension": left,
            "left_value": left_value,
            "right_dimension": right,
            "right_value": right_value,
            "total_cells": sum(
                pair_support[(left, left_value, right, right_value, regime)]
                for regime in REGIMES
            ),
            **{
                f"{regime}_cells": pair_support[
                    (left, left_value, right, right_value, regime)
                ]
                for regime in REGIMES
            },
        }
        for left, left_value, right, right_value in observed_pairs
    ]
    return value_rows, pair_rows


def design_grammar_regimes(
    schema: Mapping[str, Any],
    cells: Sequence[Mapping[str, Any]],
    *,
    generator_kcs: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    items: Sequence[Mapping[str, Any]] | None = None,
    design: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Design seen and structural holdout cohorts without response evidence."""

    normalized = _normalize_inputs(schema, cells, generator_kcs, items)
    fixed_design = _validate_design(design)
    unseen_value = _choose_unseen_value(normalized, fixed_design)
    combinations = _choose_unseen_combinations(
        normalized, fixed_design, unseen_value["indices"]
    )
    seen_indices = (
        set(range(len(normalized["cells"])))
        - set(unseen_value["indices"])
        - set(combinations["indices"])
    )
    if not seen_indices:
        raise GrammarRegimeDesignError("regime design left no seen GrammarCells")
    regime_by_index = {
        index: (
            "unseen_value"
            if index in unseen_value["indices"]
            else "unseen_combination"
            if index in combinations["indices"]
            else "seen"
        )
        for index in range(len(normalized["cells"]))
    }
    seen_value_support, seen_pair_support = _counter_after_removal(
        normalized["cells"],
        normalized["dimensions"],
        set(range(len(normalized["cells"]))) - set(unseen_value["indices"]),
        combinations["indices"],
    )

    rows = []
    for index, cell in enumerate(normalized["cells"]):
        regime = regime_by_index[index]
        unseen_values = [
            {"dimension": dimension, "value": value}
            for dimension, value in _feature_values(
                cell["features"], normalized["dimensions"]
            )
            if seen_value_support[(dimension, value)] == 0
        ]
        pairs = _feature_pairs(cell["features"], normalized["dimensions"])
        constituent_seen = not unseen_values
        pairwise_seen = constituent_seen and all(seen_pair_support[pair] > 0 for pair in pairs)
        if regime == "unseen_value" and not unseen_values:
            raise AssertionError("unseen-value cohort contains no value absent from seen")
        if regime == "unseen_combination" and not constituent_seen:
            raise AssertionError("unseen-combination cohort has an unseen constituent")
        if (
            regime == "unseen_combination"
            and bool(fixed_design["unseen_combination"]["require_pairwise_seen"])
            and not pairwise_seen
        ):
            raise AssertionError("required pairwise-seen combination is not pairwise seen")
        subtype = None
        if regime == "unseen_combination":
            subtype = (
                "pairwise_seen_full_tuple_unseen"
                if pairwise_seen
                else "constituent_seen_full_tuple_unseen"
            )
        rows.append(
            {
                "cell_id": cell["cell_id"],
                "grammar_regime": regime,
                "combination_subtype": subtype,
                "features": dict(cell["features"]),
                "unseen_values_relative_to_seen": unseen_values,
                "constituent_seen": constituent_seen if regime != "seen" else None,
                "pairwise_seen": pairwise_seen if regime == "unseen_combination" else None,
                "full_tuple_seen": regime == "seen",
                "item_support": (
                    normalized["item_count"][cell["cell_id"]]
                    if normalized["item_count"] is not None
                    else None
                ),
                "selection_reason": (
                    "feature_value_absent_from_seen"
                    if regime == "unseen_value"
                    else "pairwise_seen_but_full_tuple_held_out"
                    if subtype == "pairwise_seen_full_tuple_unseen"
                    else "constituents_seen_but_full_tuple_held_out"
                    if regime == "unseen_combination"
                    else "acquisition_measurement"
                ),
            }
        )

    value_rows, pair_rows = _supports_by_regime(normalized, regime_by_index)
    kc_ids = [str(row["id"]) for row in normalized["kcs"]]
    kc_support_by_regime = {
        regime: _kc_support(
            [index for index, assigned in regime_by_index.items() if assigned == regime],
            normalized["active_by_index"],
            kc_ids,
        )
        for regime in REGIMES
    }
    unseen_value_only_kcs = sorted(
        kc_id
        for kc_id in kc_ids
        if kc_support_by_regime["unseen_value"][kc_id] > 0
        and kc_support_by_regime["seen"][kc_id] == 0
    )
    absent_seen_kcs = sorted(
        kc_id for kc_id in kc_ids if kc_support_by_regime["seen"][kc_id] == 0
    )
    limitations = []
    if not combinations["target_reached"]:
        limitations.append("unseen_combination_target_not_reached")
    if unseen_value_only_kcs:
        limitations.append("generator_kcs_unique_to_unseen_value")
    if items is None:
        limitations.append("item_support_not_audited")

    semantic_assignment = [
        {
            "features": row["features"],
            "grammar_regime": row["grammar_regime"],
            "combination_subtype": row["combination_subtype"],
        }
        for row in rows
    ]
    audit = {
        "design_id": fixed_design["design_id"],
        "status": "PASS",
        "counts": {
            "cells": len(rows),
            **{
                f"{regime}_cells": sum(row["grammar_regime"] == regime for row in rows)
                for regime in REGIMES
            },
            "pairwise_seen_unseen_combination_cells": sum(
                row["grammar_regime"] == "unseen_combination" and row["pairwise_seen"]
                for row in rows
            ),
        },
        "unseen_value_search": {
            "trigger_values": [
                {"dimension": dimension, "value": value}
                for dimension, value in unseen_value["triggers"]
            ],
            "all_values_absent_from_seen": [
                {"dimension": dimension, "value": value}
                for dimension, value in unseen_value["derived_unseen"]
            ],
            "evaluated_candidates": unseen_value["evaluated_candidates"],
            "feasible_candidates": unseen_value["feasible_candidates"],
        },
        "unseen_combination_search": {
            "candidate_cells": combinations["candidate_cells"],
            "evaluated_states": combinations["evaluated_states"],
            "target_reached": combinations["target_reached"],
            "all_constituents_seen": all(
                row["constituent_seen"]
                for row in rows
                if row["grammar_regime"] == "unseen_combination"
            ),
            "all_pairs_seen": all(
                row["pairwise_seen"]
                for row in rows
                if row["grammar_regime"] == "unseen_combination"
            ),
            "all_full_tuples_unseen": all(
                not row["full_tuple_seen"]
                for row in rows
                if row["grammar_regime"] == "unseen_combination"
            ),
        },
        "value_support": value_rows,
        "pair_support": pair_rows,
        "generator_kc_cell_support_by_regime": {
            regime: dict(sorted(kc_support_by_regime[regime].items()))
            for regime in REGIMES
        },
        "generator_kcs_unique_to_unseen_value": unseen_value_only_kcs,
        "generator_kcs_absent_from_seen": absent_seen_kcs,
        "limitations": limitations,
        "semantic_assignment_sha256": hashlib.sha256(
            json.dumps(
                semantic_assignment,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "metadata": {
            "selection_inputs": [
                "canonical_feature_tuples",
                "generator_kc_activation_rules" if generator_kcs is not None else None,
                "item_counts_by_cell" if items is not None else None,
                "fixed_design",
            ],
            "learner_outcomes_read": False,
            "holdout_outcomes_read": False,
            "discovered_kcs_read": False,
            "item_text_read": False,
            "item_answers_read": False,
            "cell_ids_used_for_selection": False,
            "tie_breaker": "sha256_of_feature_tuples_and_declared_seed",
            "semantic_tie_seed": int(fixed_design["semantic_tie_seed"]),
        },
    }
    audit["metadata"]["selection_inputs"] = [
        value for value in audit["metadata"]["selection_inputs"] if value is not None
    ]
    return {"assignments": rows, "audit": audit, "design": fixed_design}
