from __future__ import annotations

import copy

import numpy as np
import pytest

from grammar_kt.kt import _bkt
from scripts.experiments.full_v1_bkt_state_recovery import (
    compute_terminal_bkt_states,
    kc_state_recovery_metrics,
)


PARAMETERS = {
    "initial_mastery": 0.35,
    "learn": 0.12,
    "guess": 0.18,
    "slip": 0.10,
}


def _events() -> list[dict]:
    return [
        {
            "event_id": "a::1",
            "learner_id": "a",
            "sequence_index": 1,
            "item_id": "i1",
            "correct": 1,
            "phase": "acquisition",
            "updates_history": True,
        },
        {
            "event_id": "a::2",
            "learner_id": "a",
            "sequence_index": 2,
            "item_id": "i2",
            "correct": 0,
            "phase": "acquisition",
            "updates_history": True,
        },
        {
            "event_id": "a::3",
            "learner_id": "a",
            "sequence_index": 3,
            "item_id": "i1",
            "correct": 0,
            "phase": "probe",
            "updates_history": False,
        },
    ]


def _projection() -> dict[str, tuple[str, ...]]:
    return {"i1": ("kc_a", "kc_b"), "i2": ("kc_b",)}


def test_exposed_terminal_states_conform_to_existing_bkt_probe_probability() -> None:
    events = _events()
    projection = _projection()
    states, audit = compute_terminal_bkt_states(events, projection, PARAMETERS)
    existing = _bkt(
        events,
        [
            {"item_id": item_id, "kc_ids": list(active)}
            for item_id, active in projection.items()
        ],
        PARAMETERS,
    )
    active = projection["i1"]
    exposed_probe_probability = PARAMETERS["guess"] + (
        1.0 - PARAMETERS["guess"] - PARAMETERS["slip"]
    ) * np.mean([states["a"][kc_id] for kc_id in active])
    assert exposed_probe_probability == pytest.approx(existing["a::3"])
    assert audit["acquisition_events_used"] == 2
    assert audit["probe_outcomes_ignored"] == 1
    assert audit["active_kc_full_credit_updates"] == 3


def test_probe_outcome_cannot_change_exposed_terminal_bkt_states() -> None:
    first, _audit = compute_terminal_bkt_states(_events(), _projection(), PARAMETERS)
    changed = copy.deepcopy(_events())
    changed[-1]["correct"] = 1
    second, _audit = compute_terminal_bkt_states(changed, _projection(), PARAMETERS)
    assert first == second


def test_kc_state_metrics_are_kc_labelled_and_handle_constant_estimate() -> None:
    metrics = kc_state_recovery_metrics([0.2, 0.8], [0.5, 0.5], bins=5)
    assert metrics["rmse"] == pytest.approx(0.3)
    assert metrics["mae"] == pytest.approx(0.3)
    assert metrics["pearson_correlation"] is None
    calibration = metrics["calibration"]
    assert calibration["linear_truth_on_estimate_slope"] is None
    nonempty = [row for row in calibration["bin_table"] if row["n"]]
    assert len(nonempty) == 1
    assert "mean_estimated_terminal_bkt_kc_state" in nonempty[0]
    assert "mean_oracle_kc_mastery_before" in nonempty[0]


def test_terminal_state_builder_rejects_acquisition_after_probe() -> None:
    events = _events()
    events.append(
        {
            "event_id": "a::4",
            "learner_id": "a",
            "sequence_index": 4,
            "item_id": "i1",
            "correct": 1,
            "phase": "acquisition",
            "updates_history": True,
        }
    )
    with pytest.raises(ValueError, match="acquisition follows terminal probe"):
        compute_terminal_bkt_states(events, _projection(), PARAMETERS)
