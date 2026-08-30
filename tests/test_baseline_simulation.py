from __future__ import annotations

from collections import Counter
from copy import deepcopy

import pytest

from grammar_kt.baseline_simulation import (
    OBSERVABLE_FIELDS,
    ORACLE_FIELDS,
    build_acquisition_occurrences,
    iter_baseline_rows,
    order_acquisition_occurrences,
    simulate_baseline,
    validate_baseline_config,
)
from grammar_kt.io import read_yaml

from .helpers import ROOT


def _toy_inputs() -> tuple[list[dict], dict, list[dict], dict[str, str], dict]:
    # These names deliberately exercise a non-English schema contract.  The
    # simulator sees only stable item/cell/KC identifiers, never grammar values.
    items = [
        {"item_id": "item_a", "cell_id": "cell_indicative_first"},
        {"item_id": "item_b", "cell_id": "cell_subjunctive_first"},
        {"item_id": "item_c", "cell_id": "cell_subjunctive_third"},
    ]
    inventory = {
        "inventory_id": "toy_mood_person_kstar_v1",
        "kcs": [
            {"id": "kc_mood"},
            {"id": "kc_person_first"},
            {"id": "kc_person_third"},
        ],
    }
    q_rows = [
        {
            "item_id": "item_a",
            "cell_id": "cell_indicative_first",
            "generator_kc_ids": ["kc_mood", "kc_person_first"],
        },
        {
            "item_id": "item_b",
            "cell_id": "cell_subjunctive_first",
            "generator_kc_ids": ["kc_mood", "kc_person_first"],
        },
        {
            "item_id": "item_c",
            "cell_id": "cell_subjunctive_third",
            "generator_kc_ids": ["kc_mood", "kc_person_third"],
        },
    ]
    regimes = {
        "cell_indicative_first": "seen",
        "cell_subjunctive_first": "unseen_combination",
        "cell_subjunctive_third": "unseen_value",
    }
    config = read_yaml(ROOT / "modules/simulation/baseline.yaml")
    config["learners"] = 2
    config["schedule"]["acquisition"][
        "target_opportunities_per_seen_kc"
    ] = 3
    return items, inventory, q_rows, regimes, config


def test_generic_explicit_kstar_simulation_has_separate_exact_schemas() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    config["seed"] = 917
    interactions, oracle = simulate_baseline(
        items, inventory, q_rows, regimes, config, seed=917
    )

    # Per learner: three Q-targeted seen-only events and one probe of all items.
    assert len(interactions) == 2 * (3 + 3)
    assert len(oracle) == len(interactions)
    assert all(tuple(row) == OBSERVABLE_FIELDS for row in interactions)
    assert all(tuple(row) == ORACLE_FIELDS for row in oracle)
    assert not any("kc" in key or "mastery" in key for key in interactions[0])
    assert all(
        row["grammar_regime"] == "seen"
        for row in interactions
        if row["phase"] == "acquisition"
    )
    assert {
        row["grammar_regime"]
        for row in interactions
        if row["phase"] == "probe"
    } == {"seen", "unseen_combination", "unseen_value"}


def test_streaming_iterator_exactly_preserves_materialized_api() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    config["seed"] = 919
    materialized_interactions, materialized_oracle = simulate_baseline(
        items, inventory, q_rows, regimes, config, seed=919
    )

    streamed = list(
        iter_baseline_rows(
            items, inventory, q_rows, regimes, config, seed=919
        )
    )
    assert [row[0] for row in streamed] == materialized_interactions
    assert [row[1] for row in streamed] == materialized_oracle


def test_minimum_response_and_all_active_opportunity_update_are_exact() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    config["learners"] = 1
    config["schedule"]["acquisition"][
        "target_opportunities_per_seen_kc"
    ] = 1
    config["seed"] = 71
    interactions, oracle = simulate_baseline(
        items, inventory, q_rows, regimes, config, seed=71
    )

    acquisition = next(row for row in oracle if row["phase"] == "acquisition")
    assert set(acquisition["mastery_before"]) == {"kc_mood", "kc_person_first"}
    assert acquisition["aggregated_mastery_before"] == min(
        acquisition["mastery_before"].values()
    )
    assert acquisition["response_probability"] == pytest.approx(
        0.1 + 0.8 * acquisition["aggregated_mastery_before"]
    )
    for kc_id, before in acquisition["mastery_before"].items():
        assert acquisition["mastery_after"][kc_id] == pytest.approx(
            before + 0.02 * (1.0 - before)
        )
    assert acquisition["updates_mastery"] is True
    assert interactions[0]["correct"] == acquisition["correct"]

    probes = [row for row in oracle if row["phase"] == "probe"]
    assert probes
    assert all(row["updates_mastery"] is False for row in probes)
    assert all(row["mastery_after"] == row["mastery_before"] for row in probes)


def test_keyed_streams_preserve_learner_prefix_and_ignore_input_order() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    config["seed"] = 1229
    two_interactions, two_oracle = simulate_baseline(
        items, inventory, q_rows, regimes, config, seed=1229
    )

    larger = deepcopy(config)
    larger["learners"] = 4
    four_interactions, four_oracle = simulate_baseline(
        list(reversed(items)),
        {**inventory, "kcs": list(reversed(inventory["kcs"]))},
        list(reversed(q_rows)),
        regimes,
        larger,
        seed=1229,
    )
    assert four_interactions[: len(two_interactions)] == two_interactions
    assert four_oracle[: len(two_oracle)] == two_oracle


def test_learner_id_prefix_does_not_change_schedules_states_or_draws() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    config["seed"] = 1231
    config["learners"] = 2
    first_interactions, first_oracle = simulate_baseline(
        items, inventory, q_rows, regimes, config, seed=1231
    )

    renamed = deepcopy(config)
    renamed["learner_ids"]["prefix"] = "participant_"
    renamed_interactions, renamed_oracle = simulate_baseline(
        items, inventory, q_rows, regimes, renamed, seed=1231
    )

    def without_id(rows: list[dict]) -> list[dict]:
        return [{key: value for key, value in row.items() if key != "learner_id"} for row in rows]

    assert without_id(renamed_interactions) == without_id(first_interactions)
    assert without_id(renamed_oracle) == without_id(first_oracle)


def test_shared_item_exposures_keep_response_draws_when_target_increases() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    regimes["cell_subjunctive_first"] = "seen"
    config["learners"] = 2
    config["seed"] = 1237
    config["schedule"]["acquisition"][
        "target_opportunities_per_seen_kc"
    ] = 3
    _short_interactions, short_oracle = simulate_baseline(
        items, inventory, q_rows, regimes, config, seed=1237
    )

    longer = deepcopy(config)
    longer["schedule"]["acquisition"][
        "target_opportunities_per_seen_kc"
    ] = 6
    _long_interactions, long_oracle = simulate_baseline(
        items, inventory, q_rows, regimes, longer, seed=1237
    )

    def acquisition_draws(rows: list[dict]) -> dict[tuple[str, str, int], float]:
        return {
            (row["learner_id"], row["item_id"], row["pass_index"]): row[
                "response_draw"
            ]
            for row in rows
            if row["phase"] == "acquisition"
        }

    short_draws = acquisition_draws(short_oracle)
    long_draws = acquisition_draws(long_oracle)
    assert short_draws
    assert set(short_draws) <= set(long_draws)
    assert all(long_draws[key] == draw for key, draw in short_draws.items())


def test_terminal_probe_repeats_share_snapshot_and_keyed_first_draws() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    config["learners"] = 1
    config["seed"] = 2027
    one_interactions, one_oracle = simulate_baseline(
        items, inventory, q_rows, regimes, config, seed=2027
    )

    repeated = deepcopy(config)
    repeated["schedule"]["probe"]["repeats"] = 2
    repeated_interactions, repeated_oracle = simulate_baseline(
        items, inventory, q_rows, regimes, repeated, seed=2027
    )
    one_probe = {
        row["item_id"]: row
        for row in one_oracle
        if row["phase"] == "probe" and row["pass_index"] == 1
    }
    repeated_first_probe = {
        row["item_id"]: row
        for row in repeated_oracle
        if row["phase"] == "probe" and row["pass_index"] == 1
    }
    assert repeated_first_probe == one_probe

    terminal_mastery: dict[str, float] = {}
    for row in repeated_oracle:
        if row["phase"] != "probe":
            continue
        for kc_id, value in row["mastery_before"].items():
            terminal_mastery.setdefault(kc_id, value)
            assert value == terminal_mastery[kc_id]
    assert all(row["phase"] == "probe" for row in repeated_interactions[-6:])


def test_baseline_rejects_empty_q_edges_and_nonterminal_updates() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    config["seed"] = 1
    broken_q = deepcopy(q_rows)
    broken_q[0]["generator_kc_ids"] = []
    with pytest.raises(ValueError, match="at least one KC"):
        simulate_baseline(items, inventory, broken_q, regimes, config, seed=1)

    broken_config = deepcopy(config)
    broken_config["schedule"]["probe"]["updates_mastery"] = True
    with pytest.raises(ValueError, match="must not update mastery"):
        simulate_baseline(items, inventory, q_rows, regimes, broken_config, seed=1)

    unknown_config = deepcopy(config)
    unknown_config["unused_scientific_knob"] = True
    with pytest.raises(ValueError, match="unknown=.*unused_scientific_knob"):
        simulate_baseline(items, inventory, q_rows, regimes, unknown_config, seed=1)

    with pytest.raises(ValueError, match="explicit seed differs"):
        simulate_baseline(items, inventory, q_rows, regimes, config, seed=2)


def test_fixed_occurrence_multiset_has_item_coverage_and_kc_target() -> None:
    seen_items = [
        {"item_id": "ejercicio_z", "cell_id": "celda_z"},
        {"item_id": "ejercicio_a", "cell_id": "celda_a"},
        {"item_id": "ejercicio_ambos", "cell_id": "celda_ambos"},
    ]
    active = {
        "ejercicio_z": ("destreza_uno",),
        "ejercicio_a": ("destreza_dos",),
        "ejercicio_ambos": ("destreza_uno", "destreza_dos"),
    }

    occurrences, diagnostics = build_acquisition_occurrences(
        seen_items,
        active,
        target_opportunities_per_seen_kc=20,
    )
    reversed_occurrences, reversed_diagnostics = build_acquisition_occurrences(
        list(reversed(seen_items)),
        dict(reversed(list(active.items()))),
        target_opportunities_per_seen_kc=20,
    )

    assert occurrences == reversed_occurrences
    assert diagnostics == reversed_diagnostics
    assert diagnostics["exhaustive_coverage_occurrences"] == len(seen_items)
    assert diagnostics["item_exposure_minimum"] == 1
    assert diagnostics["kc_opportunity_minimum"] >= 20
    assert set(diagnostics["item_exposures"]) == {
        "ejercicio_z",
        "ejercicio_a",
        "ejercicio_ambos",
    }
    assert all(
        row["item_exposure_index"] == row["pass_index"]
        for row in occurrences
    )
    assert all(
        row["schedule_stage"] == "exhaustive_coverage"
        for row in occurrences
        if row["item_exposure_index"] == 1
    )


def test_simulation_delivers_same_item_coverage_and_kc_target_to_every_learner() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    regimes["cell_subjunctive_first"] = "seen"
    config["learners"] = 3
    config["seed"] = 811
    config["schedule"]["acquisition"][
        "target_opportunities_per_seen_kc"
    ] = 5

    interactions, oracle = simulate_baseline(
        items, inventory, q_rows, regimes, config, seed=811
    )
    item_counts_by_learner: dict[str, Counter[str]] = {}
    kc_counts_by_learner: dict[str, Counter[str]] = {}
    for row in oracle:
        if row["phase"] != "acquisition":
            continue
        item_counts_by_learner.setdefault(row["learner_id"], Counter()).update(
            [row["item_id"]]
        )
        kc_counts_by_learner.setdefault(row["learner_id"], Counter()).update(
            row["active_generator_kc_ids"]
        )

    assert all(
        set(counts) == {"item_a", "item_b"} and min(counts.values()) >= 1
        for counts in item_counts_by_learner.values()
    )
    assert all(min(counts.values()) >= 5 for counts in kc_counts_by_learner.values())
    assert len({tuple(sorted(counts.items())) for counts in item_counts_by_learner.values()}) == 1
    assert len({tuple(sorted(counts.items())) for counts in kc_counts_by_learner.values()}) == 1
    assert all(
        row["grammar_regime"] == "seen"
        for row in interactions
        if row["phase"] == "acquisition"
    )


def test_occurrence_order_is_keyed_deterministic_and_preserves_exposure_order() -> None:
    seen_items = [
        {"item_id": "uno", "cell_id": "celda_uno"},
        {"item_id": "dos", "cell_id": "celda_dos"},
        {"item_id": "ambos", "cell_id": "celda_ambos"},
    ]
    active = {
        "uno": ("kc_uno",),
        "dos": ("kc_dos",),
        "ambos": ("kc_uno", "kc_dos"),
    }
    occurrences, _ = build_acquisition_occurrences(
        seen_items, active, target_opportunities_per_seen_kc=7
    )

    first = order_acquisition_occurrences(occurrences, seed=812, learner_number=3)
    repeated = order_acquisition_occurrences(
        list(reversed(occurrences)), seed=812, learner_number=3
    )
    assert first == repeated
    assert [row["schedule_step"] for row in first] == list(
        range(1, len(first) + 1)
    )
    exposure_by_item: dict[str, list[int]] = {}
    for row in first:
        exposure_by_item.setdefault(row["item"]["item_id"], []).append(
            row["item_exposure_index"]
        )
    assert all(values == list(range(1, len(values) + 1)) for values in exposure_by_item.values())


def test_production_config_freezes_hybrid_schedule_and_rejects_drift() -> None:
    config = read_yaml(ROOT / "modules/simulation/baseline.yaml")
    validate_baseline_config(config)
    assert config["schedule"]["acquisition"] == {
        "mode": "exhaustive_then_q_balanced",
        "exhaustive_coverage_passes": 1,
        "target_opportunities_per_seen_kc": 12,
    }
    assert config["schedule"]["item_order"] == "keyed_occurrence_rank"

    old_semantics = deepcopy(config)
    old_semantics["schedule"]["acquisition_passes"] = 5
    with pytest.raises(ValueError, match="unknown=.*acquisition_passes"):
        validate_baseline_config(old_semantics)

    two_coverage_passes = deepcopy(config)
    two_coverage_passes["schedule"]["acquisition"][
        "exhaustive_coverage_passes"
    ] = 2
    with pytest.raises(ValueError, match="exactly one coverage pass"):
        validate_baseline_config(two_coverage_passes)

    unknown_nested_knob = deepcopy(config)
    unknown_nested_knob["schedule"]["acquisition"]["learner_outcomes"] = True
    with pytest.raises(ValueError, match="unknown=.*learner_outcomes"):
        validate_baseline_config(unknown_nested_knob)


def test_simulator_sanitizes_english_outcome_and_k_hat_fields() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    config["seed"] = 817
    clean = simulate_baseline(
        items, inventory, q_rows, regimes, config, seed=817
    )

    contaminated_items = deepcopy(items)
    for row in contaminated_items:
        row.update(
            {
                "tense": "not_consumed",
                "aspect": "not_consumed",
                "correct": 1,
                "learner_outcomes": [1, 0, 1],
            }
        )
    contaminated_inventory = deepcopy(inventory)
    for row in contaminated_inventory["kcs"]:
        row["k_hat"] = "not_consumed"
    contaminated_q = deepcopy(q_rows)
    for row in contaminated_q:
        row["predicted_generator_kc_ids"] = ["not_consumed"]

    assert simulate_baseline(
        contaminated_items,
        contaminated_inventory,
        contaminated_q,
        regimes,
        config,
        seed=817,
    ) == clean
