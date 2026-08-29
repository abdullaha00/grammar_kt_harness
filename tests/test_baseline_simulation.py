from __future__ import annotations

from copy import deepcopy

import pytest

from grammar_kt.baseline_simulation import (
    OBSERVABLE_FIELDS,
    ORACLE_FIELDS,
    simulate_baseline,
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
    config["schedule"]["acquisition_passes"] = 2
    return items, inventory, q_rows, regimes, config


def test_generic_explicit_kstar_simulation_has_separate_exact_schemas() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    interactions, oracle = simulate_baseline(
        items, inventory, q_rows, regimes, config, seed=917
    )

    # Per learner: two seen-only acquisition events and one probe of all items.
    assert len(interactions) == 2 * (2 * 1 + 3)
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


def test_minimum_response_and_all_active_opportunity_update_are_exact() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    config["learners"] = 1
    config["schedule"]["acquisition_passes"] = 1
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


def test_terminal_probe_repeats_share_snapshot_and_keyed_first_draws() -> None:
    items, inventory, q_rows, regimes, config = _toy_inputs()
    config["learners"] = 1
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
    broken_q = deepcopy(q_rows)
    broken_q[0]["generator_kc_ids"] = []
    with pytest.raises(ValueError, match="at least one KC"):
        simulate_baseline(items, inventory, broken_q, regimes, config, seed=1)

    broken_config = deepcopy(config)
    broken_config["schedule"]["probe"]["updates_mastery"] = True
    with pytest.raises(ValueError, match="must not update mastery"):
        simulate_baseline(items, inventory, q_rows, regimes, broken_config, seed=1)
