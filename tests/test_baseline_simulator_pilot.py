from __future__ import annotations

from copy import deepcopy
import json
import sys

import pytest

from scripts.investigate_baseline_simulator import (
    AGGREGATIONS,
    EXHAUSTIVE_PASSES,
    GATE_DECLARATION,
    INITIAL_BETA_GRID,
    LEARNING_RULES,
    Q_BALANCED_TARGETS,
    RATE_GRID,
    SYMMETRIC_GUESS_SLIP_GRID,
    analytical_aggregation_comparison,
    build_acquisition_schedule,
    build_conditions,
    investigate_baseline_simulator,
    main,
    normalize_inputs,
    simulate_condition,
)


def _toy_inputs() -> tuple[list[dict], list[dict], list[dict], dict[str, str]]:
    # The pilot only consumes opaque IDs.  These non-English names guard
    # against hidden tense/aspect/English branches in generic simulation code.
    items = [
        {"item_id": "ejercicio_a", "cell_id": "celda_indicativo_primera"},
        {"item_id": "ejercicio_b", "cell_id": "celda_indicativo_tercera"},
        {"item_id": "ejercicio_c", "cell_id": "celda_subjuntivo_primera"},
        {"item_id": "ejercicio_d", "cell_id": "celda_subjuntivo_nueva"},
    ]
    kcs = [
        {"id": "destreza_modo"},
        {"id": "destreza_persona_primera"},
        {"id": "destreza_valor_nuevo"},
    ]
    q_rows = [
        {
            "item_id": "ejercicio_a",
            "cell_id": "celda_indicativo_primera",
            "generator_kc_ids": [
                "destreza_modo",
                "destreza_persona_primera",
            ],
        },
        {
            "item_id": "ejercicio_b",
            "cell_id": "celda_indicativo_tercera",
            "generator_kc_ids": ["destreza_modo"],
        },
        {
            "item_id": "ejercicio_c",
            "cell_id": "celda_subjuntivo_primera",
            "generator_kc_ids": [
                "destreza_modo",
                "destreza_persona_primera",
            ],
        },
        {
            "item_id": "ejercicio_d",
            "cell_id": "celda_subjuntivo_nueva",
            "generator_kc_ids": ["destreza_valor_nuevo"],
        },
    ]
    regimes = {
        "celda_indicativo_primera": "seen",
        "celda_indicativo_tercera": "seen",
        "celda_subjuntivo_primera": "unseen_combination",
        "celda_subjuntivo_nueva": "unseen_value",
    }
    return items, kcs, q_rows, regimes


def test_analytical_hard_checks_distinguish_noncompensation_and_row_count() -> None:
    result = analytical_aggregation_comparison()
    by_name = {row["aggregation"]: row for row in result["results"]}

    assert set(by_name) == set(AGGREGATIONS)
    assert result["admissible_aggregations"] == ["minimum"]
    assert all(
        row["hard_checks"]["monotonicity"]["passed"]
        and row["hard_checks"]["permutation_invariance"]["passed"]
        for row in by_name.values()
    )
    assert by_name["minimum"]["hard_checks"][
        "noncompensation_0_95_0_05_at_most_0_10"
    ]["value"] == pytest.approx(0.05)
    assert by_name["product"]["hard_checks"][
        "noncompensation_0_95_0_05_at_most_0_10"
    ]["passed"]
    assert not by_name["product"]["hard_checks"][
        "equal_skill_row_count_invariance"
    ]["passed"]
    assert not by_name["arithmetic_mean"]["hard_checks"][
        "noncompensation_0_95_0_05_at_most_0_10"
    ]["passed"]
    assert not by_name["mean_logit"]["hard_checks"][
        "noncompensation_0_95_0_05_at_most_0_10"
    ]["passed"]


def test_compact_condition_grid_contains_every_preregistered_intervention() -> None:
    conditions = build_conditions()

    assert len(conditions) == 20
    factorial = [
        row
        for row in conditions
        if "aggregation_by_learning_rule" in row["families"]
    ]
    assert {
        (row["aggregation"], row["learning_rule"]) for row in factorial
    } == set(__import__("itertools").product(AGGREGATIONS, LEARNING_RULES))
    rate = [row for row in conditions if "learning_rate" in row["families"]]
    assert {row["learning_rate"] for row in rate} == set(RATE_GRID) == {0.01, 0.02}
    assert {
        (row["beta_alpha"], row["beta_beta"])
        for row in conditions
        if "initial_mastery_beta" in row["families"]
    } == set(INITIAL_BETA_GRID)
    assert {
        row["guess"]
        for row in conditions
        if "symmetric_guess_slip" in row["families"]
    } == set(SYMMETRIC_GUESS_SLIP_GRID)
    schedule = [
        row for row in conditions if "schedule_semantics" in row["families"]
    ]
    assert {
        row["target_opportunities_per_seen_kc"]
        for row in schedule
        if row["schedule_mode"] == "q_balanced"
    } == set(Q_BALANCED_TARGETS) == {12, 20, 30}
    assert {
        row["exhaustive_passes"]
        for row in schedule
        if row["schedule_mode"] == "exhaustive_passes"
    } == set(EXHAUSTIVE_PASSES) == {1, 2}
    for row in conditions:
        if row["families"] == ["schedule_semantics"]:
            continue
        assert row["schedule_mode"] == "q_balanced"
        assert row["target_opportunities_per_seen_kc"] == 20
        assert row["exhaustive_passes"] is None
    assert GATE_DECLARATION[
        "minimum_seen_kc_opportunities_per_learner"
    ]["minimum"] == 12
    assert {
        key: GATE_DECLARATION["initial_seen_median_probability"][key]
        for key in ("minimum", "maximum")
    } == {"minimum": 0.25, "maximum": 0.60}
    assert {
        key: GATE_DECLARATION["terminal_seen_median_probability"][key]
        for key in ("minimum", "maximum")
    } == {"minimum": 0.55, "maximum": 0.80}
    assert {
        key: GATE_DECLARATION["median_seen_probability_gain"][key]
        for key in ("minimum", "maximum")
    } == {"minimum": 0.10, "maximum": 0.30}
    assert GATE_DECLARATION[
        "fraction_terminal_seen_kc_states_above_0_95"
    ]["maximum"] == 0.10


def test_q_balanced_targets_kcs_while_exhaustive_passes_balance_item_exposure() -> None:
    items, kcs, q_rows, regimes = _toy_inputs()
    normalized = normalize_inputs(items, kcs, q_rows, regimes)
    seen_items = [
        row
        for row in normalized["items"]
        if normalized["grammar_regime_by_cell"][row["cell_id"]] == "seen"
    ]
    schedule_conditions = [
        row for row in build_conditions() if "schedule_semantics" in row["families"]
    ]
    balanced_condition = next(
        row
        for row in schedule_conditions
        if row["schedule_mode"] == "q_balanced"
        and row["target_opportunities_per_seen_kc"] == 12
    )
    exhaustive_condition = next(
        row
        for row in schedule_conditions
        if row["schedule_mode"] == "exhaustive_passes"
        and row["exhaustive_passes"] == 2
    )

    balanced, balanced_diagnostics = build_acquisition_schedule(
        seen_items,
        normalized["seen_kc_ids"],
        normalized["active_by_item"],
        balanced_condition,
        seed=19,
        learner_number=1,
    )
    repeated, repeated_diagnostics = build_acquisition_schedule(
        list(reversed(seen_items)),
        normalized["seen_kc_ids"],
        normalized["active_by_item"],
        balanced_condition,
        seed=19,
        learner_number=1,
    )
    exhaustive, exhaustive_diagnostics = build_acquisition_schedule(
        seen_items,
        normalized["seen_kc_ids"],
        normalized["active_by_item"],
        exhaustive_condition,
        seed=19,
        learner_number=1,
    )

    assert balanced == repeated
    assert balanced_diagnostics == repeated_diagnostics
    assert balanced_diagnostics["kc_opportunity_minimum"] == 12
    assert balanced_diagnostics["kc_opportunity_maximum"] >= 12
    assert len(balanced) == balanced_diagnostics["schedule_length"]
    assert exhaustive_diagnostics["kc_opportunity_minimum"] == 2
    assert exhaustive_diagnostics["kc_opportunity_maximum"] == 4
    assert exhaustive_diagnostics["item_exposure_imbalance"] == 0
    assert exhaustive_diagnostics["item_exposure_minimum"] == 2
    assert len(exhaustive) == 4


def test_non_english_pilot_uses_seen_acquisition_and_frozen_terminal_probes() -> None:
    items, kcs, q_rows, regimes = _toy_inputs()
    artifact = investigate_baseline_simulator(
        items, kcs, q_rows, regimes, learners=12, seed=99
    )

    assert artifact["protocol"]["condition_count"] == 20
    assert len(artifact["schedule_comparison"]) == 5
    assert {
        row["schedule_mode"] for row in artifact["schedule_comparison"]
    } == {"q_balanced", "exhaustive_passes"}
    assert artifact["selection"]["selected_condition_id"] is None
    assert artifact["scientific_boundary"][
        "prediction_or_kc_recovery_used"
    ] is False
    assert artifact["inputs"]["unseen_value_only_kc_ids"] == [
        "destreza_valor_nuevo"
    ]
    assert artifact["runtime"]["conditions_executed"] == 20
    assert artifact["runtime"]["total_events"] > 0

    assert all(
        row["metrics"]["seen_only_acquisition_verified"]
        and row["metrics"]["terminal_non_updating_probe_verified"]
        and row["metrics"]["maximum_unseen_value_only_kc_absolute_change"] == 0.0
        for row in artifact["conditions"]
    )
    assert {
        row["learning_rule"]
        for row in artifact["conditions"]
        if "aggregation_by_learning_rule" in row["families"]
    } == set(LEARNING_RULES)

    # The factorial differs only in aggregation/update semantics.  Keyed
    # initial states and aligned response draws therefore remain common.
    factorial = [
        row
        for row in artifact["conditions"]
        if "aggregation_by_learning_rule" in row["families"]
    ]
    assert len(factorial) == 12
    assert len(
        {
            row["metrics"]["hashes"]["initial_mastery_states_sha256"]
            for row in factorial
        }
    ) == 1
    assert len(
        {
            row["metrics"]["hashes"]["acquisition_schedules_sha256"]
            for row in factorial
        }
    ) == 1
    assert len(
        {
            row["metrics"]["hashes"]["common_random_draws_sha256"]
            for row in factorial
        }
    ) == 1
    assert artifact["admissible_condition_ids"]
    assert all(
        "agg-minimum" in condition_id
        for condition_id in artifact["admissible_condition_ids"]
    )


def test_structural_sanitization_and_keyed_results_ignore_input_row_order() -> None:
    items, kcs, q_rows, regimes = _toy_inputs()
    contaminated_items = deepcopy(items)
    for item in contaminated_items:
        item.update({"correct": 1, "learner_id": "not_consumed", "kt_score": 0.9})
    contaminated_kcs = deepcopy(kcs)
    for kc in contaminated_kcs:
        kc["discovery_score"] = 999

    clean = normalize_inputs(items, kcs, q_rows, regimes)
    sanitized = normalize_inputs(
        list(reversed(contaminated_items)),
        list(reversed(contaminated_kcs)),
        list(reversed(q_rows)),
        regimes,
    )
    assert clean == sanitized

    reference = next(
        row
        for row in build_conditions()
        if {
            "aggregation_by_learning_rule",
            "initial_mastery_beta",
            "learning_rate",
            "schedule_semantics",
            "symmetric_guess_slip",
        }
        <= set(row["families"])
    )
    first = simulate_condition(clean, reference, learners=6, seed=701)
    repeated = simulate_condition(sanitized, reference, learners=6, seed=701)
    first_metrics = deepcopy(first["metrics"])
    repeated_metrics = deepcopy(repeated["metrics"])
    first_metrics.pop("runtime_seconds")
    repeated_metrics.pop("runtime_seconds")
    assert first_metrics == repeated_metrics
    assert first["simulation_gates"] == repeated["simulation_gates"]


def test_cli_accepts_dense_q_matrix_and_writes_auditable_artifact(
    tmp_path, monkeypatch
) -> None:
    items, kcs, q_rows, regimes = _toy_inputs()
    items_path = tmp_path / "items.jsonl"
    kcs_path = tmp_path / "kcs.jsonl"
    q_path = tmp_path / "q_matrix.csv"
    regimes_path = tmp_path / "regimes.json"
    output_path = tmp_path / "pilot.json"
    items_path.write_text(
        "".join(json.dumps(row) + "\n" for row in items), encoding="utf-8"
    )
    kcs_path.write_text(
        "".join(json.dumps(row) + "\n" for row in kcs), encoding="utf-8"
    )
    kc_ids = sorted(row["id"] for row in kcs)
    active_by_item = {
        row["item_id"]: set(row["generator_kc_ids"]) for row in q_rows
    }
    q_path.write_text(
        "item_id," + ",".join(kc_ids) + "\n"
        + "".join(
            row["item_id"]
            + ","
            + ",".join(
                str(int(kc_id in active_by_item[row["item_id"]]))
                for kc_id in kc_ids
            )
            + "\n"
            for row in items
        ),
        encoding="utf-8",
    )
    regimes_path.write_text(json.dumps(regimes), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "investigate_baseline_simulator.py",
            "--items",
            str(items_path),
            "--kcs",
            str(kcs_path),
            "--q-matrix",
            str(q_path),
            "--regimes",
            str(regimes_path),
            "--learners",
            "2",
            "--seed",
            "503",
            "--output",
            str(output_path),
        ],
    )

    assert main() == 0
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["inputs"]["generator_kc_count"] == 3
    assert artifact["inputs"]["q_edge_count"] == 6
    assert artifact["runtime"]["conditions_executed"] == 20
    assert artifact["inputs"]["q_matrix_file_sha256"]
