from __future__ import annotations

import copy

from grammar_kt.io import read_yaml
from grammar_kt.kc import project_kcs
from grammar_kt.kt import run_kt
from grammar_kt.simulate import simulate_frozen_probes

from .helpers import FACTORIZED_POLICY, KT_PROTOCOL, ROOT, SIMULATION_WORLD, base_bank


FROZEN_PROTOCOL = read_yaml(ROOT / "modules/simulation/protocol.yaml")


def _frozen_fixture() -> tuple[list[dict], list[dict], list[dict]]:
    _mappings, cells, _candidates, accepted, _judgments, fold = base_bank()
    events = simulate_frozen_probes(
        accepted, fold, SIMULATION_WORLD, FROZEN_PROTOCOL
    )
    projection = project_kcs(accepted, cells, FACTORIZED_POLICY)
    return events, projection, fold


def test_frozen_protocol_acquires_development_then_probes_every_regime() -> None:
    events, _projection, fold = _frozen_fixture()
    split_by_cell = {row["cell_id"]: row["grammar_split"] for row in fold}
    _mappings, _cells, _candidates, accepted, _judgments, _fold = base_bank()
    cell_by_item = {row["item_id"]: row["cell_id"] for row in accepted}
    acquisition = [row for row in events if row["protocol_phase"] == "acquisition"]
    probes = [row for row in events if row["protocol_phase"] == "probe"]

    assert acquisition
    assert {row["grammar_split"] for row in acquisition} == {"development"}
    assert {row["dataset_split"] for row in acquisition} == {"train", "validation"}
    assert all(row["updates_mastery"] and row["updates_history"] for row in acquisition)
    assert {row["grammar_split"] for row in probes} == {
        "development",
        "compositional_holdout",
        "novel_feature_holdout",
    }
    assert all(row["dataset_split"] == "test" for row in probes)
    assert all(not row["updates_mastery"] and not row["updates_history"] for row in probes)
    assert all(
        split_by_cell[cell_by_item[row["item_id"]]] == row["grammar_split"]
        for row in events
    )


def test_probe_outcomes_and_order_do_not_change_other_probe_predictions() -> None:
    events, projection, _fold = _frozen_fixture()
    first = run_kt(events, projection, KT_PROTOCOL)
    changed = copy.deepcopy(events)
    probe_rows = [row for row in changed if row["protocol_phase"] == "probe"]
    probe_rows[0]["correct"] = 1 - probe_rows[0]["correct"]
    by_learner: dict[str, list[dict]] = {}
    for row in probe_rows:
        by_learner.setdefault(row["learner_id"], []).append(row)
    for rows in by_learner.values():
        sequence_indices = sorted(row["sequence_index"] for row in rows)
        for row, sequence_index in zip(reversed(rows), sequence_indices, strict=True):
            row["sequence_index"] = sequence_index
    second = run_kt(changed, projection, KT_PROTOCOL)
    first_lookup = {
        (row["event_id"], row["technique"]): row["probability"] for row in first
    }
    second_lookup = {
        (row["event_id"], row["technique"]): row["probability"] for row in second
    }
    assert first_lookup == second_lookup


def test_primary_logistic_ignores_oracle_difficulty_but_control_uses_it() -> None:
    events, projection, _fold = _frozen_fixture()
    primary = run_kt(events, projection, KT_PROTOCOL)
    changed = copy.deepcopy(events)
    for index, row in enumerate(changed):
        if row["dataset_split"] == "test":
            row["item_difficulty"] = 20.0 if index % 2 else -20.0
    changed_primary = run_kt(changed, projection, KT_PROTOCOL)
    assert [
        row["probability"] for row in primary if row["technique"] == "logistic"
    ] == [
        row["probability"]
        for row in changed_primary
        if row["technique"] == "logistic"
    ]

    control = copy.deepcopy(KT_PROTOCOL)
    control["techniques"] = ["logistic_oracle_difficulty"]
    control["logistic_oracle_difficulty"] = {
        **control["logistic"],
        "include_item_difficulty": True,
    }
    before = run_kt(events, projection, control)
    after = run_kt(changed, projection, control)
    assert [row["probability"] for row in before] != [
        row["probability"] for row in after
    ]


def test_duplicate_activation_columns_do_not_change_mean_shared_credit_bkt() -> None:
    events, projection, _fold = _frozen_fixture()
    control = copy.deepcopy(KT_PROTOCOL)
    control["techniques"] = ["bkt"]
    first = run_kt(events, projection, control)
    duplicated = [
        {
            **row,
            "kc_ids": [
                value
                for kc_id in row["kc_ids"]
                for value in (kc_id, f"duplicate__{kc_id}")
            ],
        }
        for row in projection
    ]
    second = run_kt(events, duplicated, control)
    assert [row["probability"] for row in first] == [
        row["probability"] for row in second
    ]
