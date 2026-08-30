from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pytest

from scripts.experiments.measurement_realism_worlds import (
    CANONICAL_FORMATS,
    OBSERVABLE_FIELDS,
    ORACLE_ONLY_FIELDS,
    ROOT,
    DEFAULT_CONFIG,
    _random_tie_mrr,
    _curriculum_stage,
    adaptive_burn_in,
    bounded_response_probability,
    build_balanced_multiset,
    build_model_design,
    build_synthetic_bank_fixture,
    create_run_plan,
    error_localisation_metrics,
    fit_abcd_models,
    fit_bounded_logistic,
    fit_error_history_models,
    format_scalar_offsets,
    learner_split,
    load_executable_config,
    load_selected_cells,
    make_error_streams,
    observable_distribution_diagnostics,
    order_fixed_occurrences,
    orthogonalized_item_effects,
    paired_learner_interval,
    simulate_world,
    terminal_kc_state_recovery,
    validate_curated_bank,
    validate_run_plan,
    validate_stream_separation,
    within_format_item_contrasts,
    write_jsonl,
    run_planned_world,
)


@pytest.fixture(scope="module")
def world_inputs():
    config = load_executable_config()
    selected = load_selected_cells(config)
    bank = build_synthetic_bank_fixture(selected, config)
    return config, selected, bank


@pytest.fixture(scope="module")
def combined_fixture_world(world_inputs):
    config, selected, bank = world_inputs
    return simulate_world(
        bank,
        selected,
        config,
        world_id="combined_heterogeneous",
        seed=20260829,
        learner_count=16,
    )


def test_frozen_config_and_complete_fixture_bank_contract(world_inputs):
    config, selected, bank = world_inputs
    schema_path = ROOT / config["frozen_overlay"]["curated_bank_contract"][
        "schema_path"
    ]
    audit = validate_curated_bank(
        bank, selected, config, schema_path=schema_path, fixture=True
    )
    assert config["status"] == "FROZEN_BEFORE_RESPONSE_GENERATION"
    assert audit["item_count"] == 152
    assert audit["seen_items"] == 144
    assert audit["probe_only_items"] == 8
    assert audit["seen_cell_q_rank"] == 18
    assert audit["formats"] == {item_format: 38 for item_format in CANONICAL_FORMATS}
    assert len({row["family_id"] for row in bank}) == 38
    with pytest.raises(ValueError, match="fixture-marked"):
        validate_curated_bank(
            bank, selected, config, schema_path=schema_path, fixture=False
        )

    incomplete = bank[:-1]
    with pytest.raises(ValueError, match="exactly 152"):
        validate_curated_bank(incomplete, selected, config, fixture=True)
    changed_q = [dict(row) for row in bank]
    changed_q[0] = dict(changed_q[0], q_row=[0] * 18)
    with pytest.raises(ValueError, match="Q row disagrees"):
        validate_curated_bank(changed_q, selected, config, fixture=True)
    changed_family = [dict(row) for row in bank]
    changed_family[0] = dict(changed_family[0], family_id="wrong-family")
    with pytest.raises(ValueError, match="changes family_id"):
        validate_curated_bank(changed_family, selected, config, fixture=True)
    changed_target = [dict(row) for row in bank]
    changed_target[0] = dict(
        changed_target[0], canonical_target_sentence="Different target."
    )
    with pytest.raises(ValueError, match="changes canonical target"):
        validate_curated_bank(changed_target, selected, config, fixture=True)


def test_clean_zero_equivalence_and_orthogonal_item_effects(world_inputs):
    config, selected, bank = world_inputs
    for mastery in (0.01, 0.20, 0.50, 0.83, 0.99):
        expected = 0.10 + 0.80 * mastery
        assert (
            bounded_response_probability(mastery, guess=0.10, slip=0.10)
            == expected
        )
    _, effects, diagnostics = orthogonalized_item_effects(
        bank, selected["kc_order"], seed=20260829, scale=0.50
    )
    assert diagnostics["orthogonal_within_tolerance"]
    assert diagnostics["design_rank"] == 21  # one declared partition relation
    assert np.isclose(np.mean(list(effects.values())), 0.0, atol=1e-12)
    assert np.isclose(np.std(list(effects.values()), ddof=0), 0.50, atol=1e-12)
    offsets = format_scalar_offsets(CANONICAL_FORMATS, 0.35)
    assert np.isclose(np.mean(list(offsets.values())), 0.0)
    assert np.isclose(np.std(list(offsets.values()), ddof=0), 0.35)
    assert _random_tie_mrr(2) == pytest.approx(0.75)
    assert _random_tie_mrr(3) == pytest.approx((1 + 1 / 2 + 1 / 3) / 3)

    with pytest.raises(RuntimeError, match="optimizer failed"):
        fit_bounded_logistic(
            np.asarray([[0.0], [1.0], [2.0], [3.0]]),
            np.asarray([0, 0, 1, 1]),
            inverse_l2=1.0,
            maximum_iterations=0,
        )


def test_sha_common_random_numbers_are_world_invariant(world_inputs):
    config, selected, bank = world_inputs
    clean = simulate_world(
        bank,
        selected,
        config,
        world_id="clean_zero",
        seed=20260829,
        learner_count=2,
    )
    perturbed = simulate_world(
        bank,
        selected,
        config,
        world_id="item_format_moderate",
        seed=20260829,
        learner_count=2,
    )
    assert clean["manifest"]["common_random_hashes"] == perturbed["manifest"][
        "common_random_hashes"
    ]
    assert clean["manifest"]["observable_semantic_sha256"] != perturbed["manifest"][
        "observable_semantic_sha256"
    ]
    replay = simulate_world(
        bank,
        selected,
        config,
        world_id="clean_zero",
        seed=20260829,
        learner_count=2,
    )
    assert clean["manifest"]["observable_semantic_sha256"] == replay["manifest"][
        "observable_semantic_sha256"
    ]
    assert clean["manifest"]["oracle_semantic_sha256"] == replay["manifest"][
        "oracle_semantic_sha256"
    ]
    expected_crn = {
        "initial_mastery",
        "ability_raw_z",
        "ability_z",
        "learning_rate",
        "guess_beta",
        "slip_beta",
        "item_difficulty_z",
        "acquisition_response",
        "probe_response",
        "failed_kc_draw",
        "model_split",
        "policy_exploration",
        "policy_tie_rank_keyspace",
    }
    assert set(clean["manifest"]["common_random_hashes"]) == expected_crn


def test_equal_budget_fixed_policies_and_adaptive_propensities(world_inputs):
    config, selected, bank = world_inputs
    occurrences, diagnostics = build_balanced_multiset(bank, config)
    assert len(occurrences) == 188
    assert diagnostics["exhaustive_coverage_occurrences"] == 144
    assert diagnostics["q_balanced_top_up_occurrences"] == 44
    assert diagnostics["kc_opportunity_minimum"] == 12
    item_by_id = {row["item_id"]: row for row in bank}
    cell_features = {
        row["cell_id"]: row["features"] for row in selected["seen_cells"]
    }
    schedules = {
        policy: order_fixed_occurrences(
            occurrences,
            bank,
            seed=20260829,
            learner_id="learner_0001",
            policy_id=policy,
            cell_features_by_id=cell_features,
        )
        for policy in ("q_balanced_lab", "curriculum", "mixed_practice")
    }
    multisets = [
        Counter(
            (row["item"]["item_id"], row["item_exposure_index"])
            for row in schedule
        )
        for schedule in schedules.values()
    ]
    assert multisets[0] == multisets[1] == multisets[2]
    curriculum_stages = [
        _curriculum_stage(
            cell_features[item_by_id[row["item"]["item_id"]]["cell_id"]]
        )
        for row in schedules["curriculum"]
    ]
    assert curriculum_stages == sorted(curriculum_stages)
    for schedule in schedules.values():
        seen_exposures: dict[str, list[int]] = defaultdict(list)
        for row in schedule:
            seen_exposures[row["item"]["item_id"]].append(row["item_exposure_index"])
        assert all(values == sorted(values) for values in seen_exposures.values())

    worlds = {
        policy: simulate_world(
            bank,
            selected,
            config,
            world_id="combined_heterogeneous",
            seed=20260829,
            policy_id=policy,
            learner_count=2,
        )
        for policy in (
            "q_balanced_lab",
            "curriculum",
            "mixed_practice",
            "adaptive_weakness",
        )
    }
    assert worlds["q_balanced_lab"]["terminal_mastery"] == worlds["curriculum"][
        "terminal_mastery"
    ]
    assert worlds["q_balanced_lab"]["terminal_mastery"] == worlds["mixed_practice"][
        "terminal_mastery"
    ]
    adaptive_rows = [
        row
        for row in worlds["adaptive_weakness"]["observable"]
        if row["learner_id"] == "learner_0001" and row["phase"] == "acquisition"
    ]
    assert len(adaptive_rows) == 188
    assert all(0 < row["selection_propensity"] <= 1 for row in adaptive_rows)
    burn_items = adaptive_burn_in(bank, seed=20260829, learner_id="learner_0001")
    assert len(burn_items) == 72
    assert len({(row["cell_id"], row["format"]) for row in burn_items}) == 72
    assert all(set(row) == {"item_id", "cell_id", "format", "acquisition_updates"} for row in burn_items)
    assert np.linalg.matrix_rank(
        np.asarray([item_by_id[row["item_id"]]["q_row"] for row in burn_items])
    ) == 18


def test_observable_oracle_separation_error_controls_and_diagnostics(
    world_inputs, combined_fixture_world
):
    config, _, bank = world_inputs
    public = combined_fixture_world["observable"]
    private = combined_fixture_world["oracle"]
    validate_stream_separation(public, private)
    assert all(set(row) == set(OBSERVABLE_FIELDS) for row in public)
    assert not any(set(row) & set(ORACLE_ONLY_FIELDS) for row in public)
    streams, audit = make_error_streams(public, private, seed=20260829)
    assert set(streams) == {
        "binary_only",
        "linked_positive_control",
        "linked_80_percent",
        "within_item_shuffled_negative_control",
    }
    assert all(row["error_category"] is None for row in streams["binary_only"])
    taxonomy = config["structured_errors"]["taxonomy"]
    for row, oracle in zip(streams["linked_positive_control"], private):
        if row["correct"]:
            assert row["error_category"] is None
        else:
            assert oracle["failed_kc"] in oracle["active_generator_kcs"]
            assert row["error_category"] == taxonomy[oracle["failed_kc"]]
    for stream in streams.values():
        assert [
            {key: value for key, value in row.items() if key != "error_category"}
            for row in stream
        ] == [
            {key: value for key, value in row.items() if key != "error_category"}
            for row in streams["binary_only"]
        ]
    assert audit["incorrect_events"] > 0
    assert set(audit["common_random_hashes"]) == {
        "error_observation",
        "error_shuffle",
    }
    diagnostics = observable_distribution_diagnostics(
        streams["linked_80_percent"], bank
    )
    assert diagnostics["provenance_scope"]["learner_oracle_fields_used"] == []
    assert 0 <= diagnostics["overall_accuracy"] <= 1
    assert set(diagnostics["format_accuracy"]) == set(CANONICAL_FORMATS)
    assert diagnostics["acquisition_item_exposure"]["zero_exposure_items"] == 0
    assert diagnostics["acquisition_history_coverage_per_learner"]["q_rank"][
        "min"
    ] == 18
    localisation = error_localisation_metrics(
        streams["linked_positive_control"], private, bank, taxonomy
    )
    assert localisation["n"] > 0
    assert localisation["compatible_log_loss"] <= localisation["uniform_log_loss"]
    terminal = {
        stream_id: terminal_kc_state_recovery(
            rows,
            combined_fixture_world["terminal_mastery"],
            bank,
            config,
            error_history=("binary" if stream_id == "binary_only" else stream_id),
        )
        for stream_id, rows in streams.items()
    }
    assert all(row["learner_kc_pairs"] == 3 * 18 for row in terminal.values())
    assert terminal["linked_positive_control"]["rmse"] < terminal["binary_only"][
        "rmse"
    ]
    assert terminal["linked_80_percent"]["rmse"] < terminal["binary_only"]["rmse"]


def test_deterministic_gzip_and_error_history_comparison(
    world_inputs, combined_fixture_world, tmp_path: Path
):
    config, _, bank = world_inputs
    rows = combined_fixture_world["observable"][:5]
    left = tmp_path / "left.jsonl.gz"
    right = tmp_path / "different-name.jsonl.gz"
    write_jsonl(left, rows, gzip_output=True)
    write_jsonl(right, rows, gzip_output=True)
    assert left.read_bytes() == right.read_bytes()

    streams, _ = make_error_streams(
        combined_fixture_world["observable"],
        combined_fixture_world["oracle"],
        seed=20260829,
    )
    # C exercises the same causal error-history implementation with a compact
    # nuisance set; the frozen confirmatory runner holds the full D model fixed.
    comparison = fit_error_history_models(
        streams,
        bank,
        config,
        condition="C",
        bootstrap_repeats=10,
    )
    assert comparison["condition_held_fixed"] == "C"
    assert set(comparison["streams"]) == set(streams)
    assert len(
        {row["evaluation_row_sha256"] for row in comparison["streams"].values()}
    ) == 1
    assert set(comparison["paired_log_loss_intervals"]) == {
        "linked_positive_control_minus_binary_only",
        "linked_80_percent_minus_binary_only",
        "within_item_shuffled_negative_control_minus_binary_only",
    }


def test_abcd_bounded_models_are_full_rank_and_learner_paired(world_inputs):
    config, selected, bank = world_inputs
    world = simulate_world(
        bank,
        selected,
        config,
        world_id="format_strong_control",
        seed=20260829,
        learner_count=16,
    )
    item_encoding, item_names, item_audit = within_format_item_contrasts(bank)
    assert len(item_names) == 123
    assert item_audit["orthonormal"]
    assert item_audit["maximum_absolute_control_inner_product"] < 1e-8
    assert all(
        np.all(item_encoding[row["item_id"]] == 0)
        for row in bank
        if not row["acquisition_updates"]
    )
    for condition in "ABCD":
        design = build_model_design(world["observable"], bank, config, condition=condition)
        assert len(design.feature_names) == design.matrix.shape[1]
        assert "active_kc_count" not in design.feature_names
    results = fit_abcd_models(
        world["observable"], bank, config, bootstrap_repeats=20
    )
    assert len({row["evaluation_row_sha256"] for row in results["conditions"].values()}) == 1
    assert all(row["training_design_full_rank"] for row in results["conditions"].values())
    assert all(row["final_fit"].converged for row in results["conditions"].values())
    assert all(0 < row["metrics"]["log_loss"] < 2 for row in results["conditions"].values())
    assert results["conditions"]["C"]["metrics"]["log_loss"] < results["conditions"][
        "A"
    ]["metrics"]["log_loss"]
    assert results["conditions"]["C"]["metrics"]["log_loss"] < results["conditions"][
        "B"
    ]["metrics"]["log_loss"]
    assert all(
        set(row["metrics_by_grammar_regime"])
        == {"seen", "unseen_combination", "unseen_value"}
        for row in results["conditions"].values()
    )
    test_events = results["conditions"]["A"]["test_events"]
    same = paired_learner_interval(
        test_events,
        results["conditions"]["A"]["test_probabilities"],
        results["conditions"]["A"]["test_probabilities"],
        repeats=20,
        seed=7,
    )
    assert same["point_estimate"] == 0.0
    assert same["percentile_95"] == [0.0, 0.0]
    assert Counter(
        learner_split(f"learner_{index:04d}", config) for index in range(1, 17)
    ) == {"train": 9, "dev": 4, "test": 3}

    item_world = simulate_world(
        bank,
        selected,
        config,
        world_id="item_moderate",
        seed=20260829,
        learner_count=16,
    )
    item_results = fit_abcd_models(
        item_world["observable"], bank, config, bootstrap_repeats=5
    )
    assert item_results["conditions"]["D"]["metrics"]["log_loss"] < item_results[
        "conditions"
    ]["C"]["metrics"]["log_loss"]


def test_production_plan_rejects_a_renamed_fixture_without_freeze_evidence(
    world_inputs, tmp_path: Path
):
    config, selected, fixture = world_inputs
    bank = []
    for row in fixture:
        copied = dict(row)
        copied["item_id"] = copied["item_id"].replace("fixture::", "contract::")
        copied["family_id"] = copied["family_id"].replace("fixture::", "contract::")
        bank.append(copied)
    bank_path = tmp_path / "contract_items.jsonl"
    output_dir = tmp_path / "planned"
    write_jsonl(bank_path, bank, gzip_output=False)
    with pytest.raises(ValueError, match="matched-bank freeze"):
        create_run_plan(
            config_path=DEFAULT_CONFIG.resolve(),
            bank_path=bank_path.resolve(),
            output_dir=output_dir.resolve(),
        )
    assert not (output_dir / "study_plan.json").exists()
