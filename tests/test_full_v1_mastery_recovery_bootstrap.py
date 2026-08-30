from __future__ import annotations

import numpy as np
import pytest

from scripts.experiments.full_v1_mastery_recovery_bootstrap import (
    paired_whole_learner_bootstrap,
)


def test_paired_whole_learner_bootstrap_is_deterministic_and_signed() -> None:
    learners = ["a", "a", "b", "b", "c", "c"]
    oracle = np.asarray([0.2, 0.8, 0.3, 0.7, 0.4, 0.6])
    reference = oracle + np.asarray([0.02, -0.02, 0.01, -0.01, 0.03, -0.03])
    candidate = oracle + np.asarray([0.20, -0.20, 0.15, -0.15, 0.10, -0.10])
    first = paired_whole_learner_bootstrap(
        learners, oracle, reference, candidate, repeats=500, seed=19
    )
    repeated = paired_whole_learner_bootstrap(
        learners, oracle, reference, candidate, repeats=500, seed=19
    )
    assert first == repeated
    assert first["sampling_unit"] == "whole learner"
    assert first["rmse"]["candidate_minus_kstar"] > 0
    assert first["rmse"]["percentile_interval_95"][0] > 0
    assert first["rmse"]["interval_crosses_zero"] is False
    assert first["mae"]["candidate_minus_kstar"] > 0


def test_paired_whole_learner_bootstrap_can_support_candidate_gain() -> None:
    learners = ["a", "a", "b", "b"]
    oracle = [0.2, 0.8, 0.3, 0.7]
    reference = [0.4, 0.6, 0.5, 0.5]
    candidate = [0.21, 0.79, 0.31, 0.69]
    result = paired_whole_learner_bootstrap(
        learners, oracle, reference, candidate, repeats=100, seed=7
    )
    assert result["rmse"]["candidate_minus_kstar"] < 0
    assert result["rmse"]["interval_relation_to_zero"] == "entirely_below_zero"


def test_paired_whole_learner_bootstrap_rejects_unpaired_or_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="paired vectors"):
        paired_whole_learner_bootstrap(["a"], [0.5], [0.5], [])
    with pytest.raises(ValueError, match="repeats"):
        paired_whole_learner_bootstrap(
            ["a", "b"], [0.4, 0.6], [0.5, 0.5], [0.5, 0.5], repeats=0
        )
    with pytest.raises(ValueError, match="candidate values"):
        paired_whole_learner_bootstrap(
            ["a", "b"], [0.4, 0.6], [0.5, 0.5], [0.5, 1.2]
        )
