from __future__ import annotations

from copy import deepcopy

import pytest

from grammar_kt.baseline_simulation import simulate_baseline
from grammar_kt.io import read_yaml
from grammar_kt.sensitivity_simulation import (
    SensitivityCondition,
    aggregate_mastery,
    response_probability,
    simulate_sensitivity,
)
from scripts.experiments.simulator_robustness import (
    BKT_MODEL,
    EMPIRICAL_MODEL,
    PRIMARY_MODEL,
    REPRESENTATION_ORDER,
    _observable_event_sha256,
    _secondary_probabilities,
    create_plan,
    evaluate_representations,
    planned_conditions,
)

from .helpers import ROOT


def _toy_inputs(learners: int = 8) -> tuple[list[dict], list[str], dict, dict, dict]:
    items = [
        {"item_id": "i1", "cell_id": "c1"},
        {"item_id": "i2", "cell_id": "c2"},
        {"item_id": "i3", "cell_id": "c3"},
        {"item_id": "i4", "cell_id": "c4"},
    ]
    kcs = ["a", "b", "c"]
    q = {
        "i1": ("a",),
        "i2": ("b",),
        "i3": ("c",),
        "i4": ("a", "b", "c"),
    }
    regimes = {
        "c1": "seen",
        "c2": "seen",
        "c3": "seen",
        "c4": "unseen_combination",
    }
    config = read_yaml(ROOT / "modules/simulation/baseline.yaml")
    config["learners"] = learners
    config["seed"] = 314159
    config["schedule"]["acquisition"]["target_opportunities_per_seen_kc"] = 3
    return items, kcs, q, regimes, config


def test_response_aggregations_and_zero_difficulty_preserve_baseline_equation() -> None:
    values = [0.2, 0.5, 0.8]
    assert aggregate_mastery(values, "minimum") == 0.2
    assert aggregate_mastery(values, "product") == pytest.approx(0.08)
    assert aggregate_mastery(values, "arithmetic_mean") == pytest.approx(0.5)
    baseline = SensitivityCondition("baseline")
    assert response_probability(values, baseline) == pytest.approx(0.1 + 0.8 * 0.2)
    with pytest.raises(ValueError, match="unknown aggregation"):
        aggregate_mastery(values, "maximum")


def test_common_keyed_latents_and_event_keys_survive_world_perturbations() -> None:
    items, kcs, q, regimes, config = _toy_inputs(learners=20)
    baseline_events, baseline_audit = simulate_sensitivity(
        items, kcs, q, regimes, config, SensitivityCondition("baseline")
    )
    changed_events, changed_audit = simulate_sensitivity(
        items,
        kcs,
        q,
        regimes,
        config,
        SensitivityCondition(
            "changed",
            aggregation="product",
            guess=0.2,
            slip=0.2,
            item_difficulty_logit_sd=0.6,
        ),
    )
    assert (
        baseline_audit["common_random_number_hashes"]
        == changed_audit["common_random_number_hashes"]
    )
    assert [
        (row["learner_id"], row["sequence_index"], row["item_id"], row["phase"])
        for row in baseline_events
    ] == [
        (row["learner_id"], row["sequence_index"], row["item_id"], row["phase"])
        for row in changed_events
    ]
    assert baseline_audit["private_event_state_emitted"] is False
    assert baseline_audit["outcome_sha256"] != changed_audit["outcome_sha256"]


def test_sensitivity_baseline_exactly_matches_frozen_baseline_semantics() -> None:
    items, kcs, q, regimes, config = _toy_inputs(learners=4)
    sensitivity_events, _audit = simulate_sensitivity(
        items, kcs, q, regimes, config, SensitivityCondition("baseline")
    )
    q_rows = [
        {
            "item_id": item["item_id"],
            "cell_id": item["cell_id"],
            "generator_kc_ids": list(q[item["item_id"]]),
        }
        for item in items
    ]
    baseline_events, _oracle = simulate_baseline(
        items,
        [{"id": kc_id} for kc_id in kcs],
        q_rows,
        regimes,
        config,
        seed=config["seed"],
    )
    assert sensitivity_events == baseline_events


def test_correlated_initial_mastery_is_marginal_mixture_not_prerequisite() -> None:
    items, kcs, q, regimes, config = _toy_inputs(learners=500)
    _baseline_events, baseline_audit = simulate_sensitivity(
        items, kcs, q, regimes, config, SensitivityCondition("baseline")
    )
    _correlated_events, correlated_audit = simulate_sensitivity(
        items,
        kcs,
        q,
        regimes,
        config,
        SensitivityCondition(
            "correlated",
            initial_mastery_global_mixture_weight=0.5,
        ),
    )
    assert (
        baseline_audit["common_random_number_hashes"]
        == correlated_audit["common_random_number_hashes"]
    )
    assert (
        baseline_audit["realized_initial_mastery_sha256"]
        != correlated_audit["realized_initial_mastery_sha256"]
    )
    baseline_summary = baseline_audit["realized_initial_mastery_summary"]
    correlated_summary = correlated_audit["realized_initial_mastery_summary"]
    assert correlated_summary["mean_pairwise_kc_correlation"] > (
        baseline_summary["mean_pairwise_kc_correlation"] + 0.10
    )
    assert correlated_summary["realized_global_selection_fraction"] == pytest.approx(
        0.5, abs=0.04
    )
    assert correlated_summary["directed_prerequisite_learning"] is False


def test_outcome_free_acquisition_item_hook_restricts_acquisition_not_probe() -> None:
    items, kcs, q, regimes, config = _toy_inputs(learners=2)
    events, audit = simulate_sensitivity(
        items,
        kcs,
        q,
        regimes,
        config,
        SensitivityCondition("hook"),
        acquisition_item_ids={"i1"},
    )
    assert {
        row["item_id"] for row in events if row["phase"] == "acquisition"
    } == {"i1"}
    assert {
        row["item_id"] for row in events if row["phase"] == "probe"
    } == {"i1", "i2", "i3", "i4"}
    assert audit["acquisition_item_ids_hook"] == ["i1"]
    with pytest.raises(ValueError, match="declared acquisition regime"):
        simulate_sensitivity(
            items,
            kcs,
            q,
            regimes,
            config,
            SensitivityCondition("bad_hook"),
            acquisition_item_ids={"i4"},
        )


def test_secondary_histories_do_not_update_from_probe_outcomes() -> None:
    events = [
        {
            "learner_id": "l1",
            "item_id": "i1",
            "sequence_index": 1,
            "correct": 1,
            "phase": "acquisition",
            "pass_index": 1,
            "grammar_regime": "seen",
        },
        {
            "learner_id": "l1",
            "item_id": "i1",
            "sequence_index": 2,
            "correct": 0,
            "phase": "probe",
            "pass_index": 1,
            "grammar_regime": "seen",
        },
        {
            "learner_id": "l1",
            "item_id": "i1",
            "sequence_index": 3,
            "correct": 1,
            "phase": "probe",
            "pass_index": 2,
            "grammar_regime": "seen",
        },
    ]
    first_empirical, first_bkt, audit = _secondary_probabilities(
        events, {"i1": ("a",)}
    )
    changed = deepcopy(events)
    changed[1]["correct"] = 1
    second_empirical, second_bkt, _ = _secondary_probabilities(
        changed, {"i1": ("a",)}
    )
    assert first_empirical.tolist() == second_empirical.tolist()
    assert first_bkt.tolist() == second_bkt.tolist()
    assert audit["bkt_known_generator_mismatch"] is True


def test_all_three_models_consume_identical_observable_events() -> None:
    items, kcs, q, regimes, config = _toy_inputs(learners=20)
    events, _audit = simulate_sensitivity(
        items, kcs, q, regimes, config, SensitivityCondition("evaluate")
    )
    projections = {
        "true_kstar": q,
        "coarse_linguistic_families": {
            item_id: ("grammar",) for item_id in q
        },
        "structural_split2": {
            "i1": ("a_1",),
            "i2": ("b_1",),
            "i3": ("c_1",),
            "i4": ("a_2", "b_2", "c_2"),
        },
    }
    result = evaluate_representations(events, projections)
    assert tuple(result["models"]) == (PRIMARY_MODEL, EMPIRICAL_MODEL, BKT_MODEL)
    assert result["same_observable_rows_across_representations_and_models"] is True
    assert result["bkt_generator_mismatch"] == {
        "mean_instead_of_minimum_multi_kc_response": True,
        "full_credit_outcome_update_instead_of_all_active_opportunity_update": True,
        "may_drive_scientific_choice": False,
    }
    expected_hash = _observable_event_sha256(events)
    assert {
        metric["observable_event_sha256"]
        for model in result["models"].values()
        for metric in model["metrics"].values()
    } == {expected_hash}
    contaminated = deepcopy(events)
    contaminated[0]["mastery_before"] = {"a": 0.5}
    with pytest.raises(ValueError, match="non-observable"):
        _observable_event_sha256(contaminated)


def test_plan_freezes_13_worlds_secondary_roles_and_outcome_free_inputs(tmp_path) -> None:
    conditions = planned_conditions()
    assert len(conditions) == 13
    condition_by_id = {
        row["condition"]["condition_id"]: row["condition"] for row in conditions
    }
    assert {
        (row["guess"], row["slip"])
        for key, row in condition_by_id.items()
        if key.startswith("noise_")
    } == {(0.0, 0.0), (0.2, 0.1), (0.1, 0.2), (0.2, 0.2)}
    correlated = condition_by_id[
        "correlated_initial_mastery_global_mixture_050"
    ]
    assert correlated["initial_mastery_global_mixture_weight"] == 0.5

    plan = create_plan(ROOT / "data/grammar_kt_full_v1", tmp_path)
    assert plan["execution_design"]["worlds"] == 39
    assert plan["execution_design"]["primary_logistic_fits"] == 117
    assert plan["execution_design"]["secondary_model_evaluations"] == 234
    assert plan["execution_design"]["novelty_grid_executed"] is False
    assert plan["scientific_boundary"]["private_baseline_oracle_read"] is False
    assert "interactions" not in plan["inputs"]
    assert "oracle" not in plan["inputs"]
    bkt = next(
        row
        for row in plan["predictors"]["secondary"]
        if row["model_id"] == BKT_MODEL
    )
    assert bkt["known_generator_mismatch"]
    assert "prohibited" in bkt["role"]
    assert tuple(REPRESENTATION_ORDER) == (
        "true_kstar",
        "coarse_linguistic_families",
        "structural_split2",
    )
