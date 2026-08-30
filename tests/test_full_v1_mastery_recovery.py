from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.experiments.full_v1_mastery_recovery import (
    ORACLE_SCHEMA,
    _deterministic_gzip,
    _strict_oracle_probe_join_after_predictions,
    inverse_response_link,
    recovery_metrics,
)


def _public_events() -> list[dict]:
    return [
        {
            "learner_id": "learner_1",
            "item_id": "item_a",
            "sequence_index": 1,
            "correct": 1,
            "phase": "acquisition",
            "pass_index": 1,
            "grammar_regime": "seen",
        },
        {
            "learner_id": "learner_1",
            "item_id": "item_b",
            "sequence_index": 2,
            "correct": 0,
            "phase": "probe",
            "pass_index": 1,
            "grammar_regime": "unseen_combination",
        },
    ]


def _oracle_rows() -> list[dict]:
    rows = []
    for public, mastery in zip(_public_events(), (0.4, 0.7), strict=True):
        active = ["gkc_a"]
        rows.append(
            {
                **public,
                "active_generator_kc_ids": active,
                "mastery_before": {"gkc_a": mastery},
                "aggregated_mastery_before": mastery,
                "response_probability": 0.1 + 0.8 * mastery,
                "response_draw": 0.2,
                "updates_mastery": public["phase"] == "acquisition",
                "mastery_after": {"gkc_a": mastery},
            }
        )
    assert all(set(row) == ORACLE_SCHEMA for row in rows)
    return rows


def _write_oracle(path: Path, rows: list[dict]) -> None:
    payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_bytes(_deterministic_gzip(payload.encode()))


def test_inverse_response_link_uses_declared_link_and_reports_clipping() -> None:
    estimate, audit = inverse_response_link(
        [0.02, 0.1, 0.5, 0.9, 0.98], guess=0.1, slip=0.1
    )
    np.testing.assert_allclose(estimate, [0.0, 0.0, 0.5, 1.0, 1.0])
    assert audit["clipped_below_zero"] == 1
    assert audit["clipped_above_one"] == 1
    with pytest.raises(ValueError, match="sum to less than one"):
        inverse_response_link([0.5], guess=0.5, slip=0.5)


def test_recovery_metrics_cover_error_correlation_and_state_calibration() -> None:
    oracle = np.asarray([0.1, 0.3, 0.7, 0.9])
    estimate = np.asarray([0.2, 0.4, 0.6, 0.8])
    metrics = recovery_metrics(oracle, estimate, bins=5)
    assert metrics["n"] == 4
    assert metrics["rmse"] == pytest.approx(0.1)
    assert metrics["mae"] == pytest.approx(0.1)
    assert metrics["pearson_correlation"] == pytest.approx(
        np.corrcoef(estimate, oracle)[0, 1]
    )
    calibration = metrics["calibration"]
    assert calibration["mean_estimate_minus_oracle"] == pytest.approx(0.0)
    expected_gap = sum(
        row["n"] / 4 * abs(row["estimate_minus_oracle"])
        for row in calibration["bin_table"]
        if row["n"]
    )
    assert calibration["fixed_bin_expected_absolute_gap"] == pytest.approx(
        expected_gap
    )
    assert sum(row["n"] for row in calibration["bin_table"]) == 4


def test_recovery_metrics_do_not_invent_constant_vector_correlation() -> None:
    metrics = recovery_metrics([0.2, 0.8], [0.5, 0.5])
    assert metrics["pearson_correlation"] is None
    assert metrics["calibration"]["linear_truth_on_estimate_slope"] is None


def test_strict_oracle_join_requires_frozen_predictions_and_exact_composite_keys(
    tmp_path: Path,
) -> None:
    public = _public_events()
    predictions = [
        {
            "learner_id": "learner_1",
            "sequence_index": 2,
            "item_id": "item_b",
            "phase": "probe",
            "pass_index": 1,
            "grammar_regime": "unseen_combination",
            "estimated_item_prerequisite_state": {"true_kstar": 0.6},
        }
    ]
    prediction_path = tmp_path / "predictions.jsonl.gz"
    prediction_path.write_bytes(gzip.compress(b"public-only\n", mtime=0))
    import hashlib

    prediction_hash = hashlib.sha256(prediction_path.read_bytes()).hexdigest()
    oracle_path = tmp_path / "oracle.jsonl.gz"
    _write_oracle(oracle_path, _oracle_rows())
    targets, audit = _strict_oracle_probe_join_after_predictions(
        oracle_path,
        public,
        predictions,
        prediction_artifact_path=prediction_path,
        prediction_artifact_sha256=prediction_hash,
    )
    assert targets == {("learner_1", 2): 0.7}
    assert audit["all_public_oracle_keys_match"] is True
    prediction_path.unlink()
    with pytest.raises(FileNotFoundError, match="must exist before oracle open"):
        _strict_oracle_probe_join_after_predictions(
            oracle_path,
            public,
            predictions,
            prediction_artifact_path=prediction_path,
            prediction_artifact_sha256=prediction_hash,
        )


def test_strict_oracle_join_rejects_paired_field_mismatch(tmp_path: Path) -> None:
    public = _public_events()
    predictions = [
        {
            "learner_id": "learner_1",
            "sequence_index": 2,
            "item_id": "item_b",
            "phase": "probe",
            "pass_index": 1,
            "grammar_regime": "unseen_combination",
        }
    ]
    prediction_path = tmp_path / "predictions.jsonl.gz"
    prediction_path.write_bytes(_deterministic_gzip(b"public-only\n"))
    import hashlib

    prediction_hash = hashlib.sha256(prediction_path.read_bytes()).hexdigest()
    oracle_rows = _oracle_rows()
    oracle_rows[1]["item_id"] = "wrong_item"
    oracle_path = tmp_path / "oracle.jsonl.gz"
    _write_oracle(oracle_path, oracle_rows)
    with pytest.raises(ValueError, match="mismatch.*item_id"):
        _strict_oracle_probe_join_after_predictions(
            oracle_path,
            public,
            predictions,
            prediction_artifact_path=prediction_path,
            prediction_artifact_sha256=prediction_hash,
        )
