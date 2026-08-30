#!/usr/bin/env python3
"""Post-plan paired-bootstrap robustness for full-v1 mastery recovery.

This analysis was requested after the primary mastery-recovery plan and result
were frozen.  It therefore writes a separate, explicitly post-plan robustness
plan and result; it does not alter or retrospectively expand the primary
estimand.  Whole learners are resampled with replacement, and candidate-minus-
K* RMSE and MAE are recomputed on all events belonging to sampled learners.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.experiments.full_v1_mastery_recovery import (  # noqa: E402
    CORE_REPRESENTATIONS,
    DEFAULT_DATASET,
    DEFAULT_OUTPUT,
    GRAMMAR_REGIMES,
    REPRESENTATION_LABELS,
    STUDY_ID as PRIMARY_STUDY_ID,
    _declared_oracle,
    _event_key,
    _event_key_sha256,
    _read_manifest,
    _strict_oracle_probe_join_after_predictions,
    _write_frozen_json,
    file_sha256,
    load_observable_events,
)


ROBUSTNESS_STUDY_ID = "full_v1_mastery_recovery_post_plan_paired_bootstrap_v1"
REFERENCE_ID = "true_kstar"
CANDIDATE_IDS = tuple(
    representation_id
    for representation_id in CORE_REPRESENTATIONS
    if representation_id != REFERENCE_ID
)
BOOTSTRAP_REPEATS = 2000
BOOTSTRAP_SEED = 20260830
PREDICTION_SCHEMA = {
    "learner_id",
    "sequence_index",
    "item_id",
    "phase",
    "pass_index",
    "grammar_regime",
    "predicted_response_probability",
    "estimated_item_prerequisite_state",
}


def _repository_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _primary_artifacts(output_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    plan_path = output_dir / "study_plan.json"
    result_path = output_dir / "results.json"
    prediction_path = output_dir / "observable_probe_state_estimates.jsonl.gz"
    artifact_manifest_path = output_dir / "artifact_manifest.json"
    for path in (plan_path, result_path, prediction_path, artifact_manifest_path):
        if not path.is_file():
            raise FileNotFoundError(f"primary mastery-recovery artifact missing: {path}")
    primary_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    primary_result = json.loads(result_path.read_text(encoding="utf-8"))
    if primary_plan.get("study_id") != PRIMARY_STUDY_ID:
        raise ValueError("unexpected primary mastery-recovery plan")
    if primary_plan.get("status") != "LOCKED_BEFORE_PRIVATE_ORACLE_READ":
        raise ValueError("primary mastery-recovery plan is not locked")
    if primary_result.get("study_id") != PRIMARY_STUDY_ID:
        raise ValueError("unexpected primary mastery-recovery result")
    if primary_result.get("status") != "FINAL_FULL_DATASET_ORACLE_EVALUATION":
        raise ValueError("primary mastery-recovery result is not final")
    if primary_result["plan_sha256"] != file_sha256(plan_path):
        raise ValueError("primary result and primary plan hash disagree")
    predicted = primary_result["observable_prediction_artifact"]
    if predicted["path"] != prediction_path.name:
        raise ValueError("primary result names an unexpected prediction artifact")
    if predicted["sha256"] != file_sha256(prediction_path):
        raise ValueError("primary public-only prediction artifact hash mismatch")
    artifact_manifest = json.loads(artifact_manifest_path.read_text(encoding="utf-8"))
    for path in (plan_path, result_path, prediction_path):
        declared = artifact_manifest["artifacts"][path.name]
        if declared["sha256"] != file_sha256(path):
            raise ValueError(f"primary artifact manifest mismatch: {path.name}")
    primary_script = ROOT / str(primary_plan["implementation"]["script"])
    if primary_plan["implementation"]["script_sha256"] != file_sha256(primary_script):
        raise ValueError("primary mastery-recovery implementation changed")
    return primary_plan, primary_result


def _input_records(dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    primary_plan, _primary_result = _primary_artifacts(output_dir)
    paths = {
        "dataset_manifest": dataset_dir / "manifest.json",
        "observable_interactions": dataset_dir / "interactions.jsonl.gz",
        "primary_study_plan": output_dir / "study_plan.json",
        "primary_results": output_dir / "results.json",
        "primary_public_estimates": output_dir
        / "observable_probe_state_estimates.jsonl.gz",
        "primary_artifact_manifest": output_dir / "artifact_manifest.json",
        "primary_implementation": ROOT
        / str(primary_plan["implementation"]["script"]),
    }
    return {
        name: {
            "path": str(path.relative_to(ROOT)),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for name, path in paths.items()
    }


def create_plan(dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    manifest = _read_manifest(dataset_dir)
    primary_plan, primary_result = _primary_artifacts(output_dir)
    script_path = Path(__file__).resolve()
    plan = {
        "study_id": ROBUSTNESS_STUDY_ID,
        "status": "POST_PLAN_USER_REQUESTED_ROBUSTNESS_LOCKED_BEFORE_REANALYSIS",
        "relationship_to_primary": {
            "primary_study_id": PRIMARY_STUDY_ID,
            "primary_plan_sha256": file_sha256(output_dir / "study_plan.json"),
            "primary_result_sha256": file_sha256(output_dir / "results.json"),
            "primary_plan_licensed_uncertainty": False,
            "primary_plan_or_result_modified": False,
            "classification": "post-plan robustness, not preregistered primary inference",
            "reason": (
                "Requested after the frozen primary result to quantify the apparent "
                "coarse-versus-K* unseen-value RMSE reversal."
            ),
        },
        "reference": REFERENCE_ID,
        "candidates_in_execution_order": list(CANDIDATE_IDS),
        "condition_labels": REPRESENTATION_LABELS,
        "events": "the same terminal non-updating probes as the primary study",
        "regimes": ["all_probe", *GRAMMAR_REGIMES],
        "method": {
            "name": "paired percentile bootstrap over whole learners",
            "sampling_unit": "learner",
            "resampling": (
                "sample 1000 learners with replacement; retain every selected "
                "learner's probe rows in the requested regime"
            ),
            "aggregation": "event-weighted within each bootstrap sample",
            "repeats": BOOTSTRAP_REPEATS,
            "seed": BOOTSTRAP_SEED,
            "common_draws": (
                "the same sorted learner IDs and seed generate identical learner "
                "resamples for every candidate and regime"
            ),
            "metrics": ["RMSE", "MAE"],
            "delta_sign": "candidate minus K*; positive favors K*",
            "interval": "2.5th and 97.5th percentiles, linear quantiles",
            "zero_rule": "interval crosses zero iff lower <= 0 <= upper",
        },
        "target_and_estimate_scope": primary_result["quantity_definition"],
        "leakage_controls": {
            "reuse_already_frozen_public_only_estimates": True,
            "oracle_use": "paired evaluation target only",
            "no_fit_tuning_or_condition_selection": True,
        },
        "inputs": _input_records(dataset_dir, output_dir),
        "private_oracle_declared_in_manifest": _declared_oracle(manifest),
        "implementation": {
            "script": str(script_path.relative_to(ROOT)),
            "script_sha256": file_sha256(script_path),
            "repository_head_at_post_plan_lock": _repository_head(),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
        },
        "exact_commands": {
            "plan": ".venv/bin/python scripts/experiments/full_v1_mastery_recovery_bootstrap.py --stage plan",
            "run": ".venv/bin/python scripts/experiments/full_v1_mastery_recovery_bootstrap.py --stage run",
            "test": ".venv/bin/python -m pytest -q tests/test_full_v1_mastery_recovery_bootstrap.py",
        },
        "primary_condition_count": len(primary_plan["conditions_in_execution_order"]),
    }
    _write_frozen_json(
        output_dir / "post_plan_bootstrap_plan.json",
        plan,
        "post-plan bootstrap specification",
    )
    return plan


def _validate_plan(
    dataset_dir: Path, output_dir: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan_path = output_dir / "post_plan_bootstrap_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError("run requires post_plan_bootstrap_plan.json")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("study_id") != ROBUSTNESS_STUDY_ID:
        raise ValueError("unexpected post-plan robustness study ID")
    if plan.get("status") != (
        "POST_PLAN_USER_REQUESTED_ROBUSTNESS_LOCKED_BEFORE_REANALYSIS"
    ):
        raise ValueError("post-plan robustness specification is not locked")
    if plan["implementation"]["script_sha256"] != file_sha256(Path(__file__).resolve()):
        raise ValueError("bootstrap implementation changed after post-plan lock")
    if plan["inputs"] != _input_records(dataset_dir, output_dir):
        raise ValueError("bootstrap inputs changed after post-plan lock")
    manifest = _read_manifest(dataset_dir)
    if plan["private_oracle_declared_in_manifest"] != _declared_oracle(manifest):
        raise ValueError("manifest-declared oracle metadata changed")
    primary_plan, primary_result = _primary_artifacts(output_dir)
    return plan, primary_plan, primary_result


def load_public_prediction_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, int]] = set()
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if set(row) != PREDICTION_SCHEMA:
                raise ValueError("primary public-prediction schema changed")
            if row["phase"] != "probe":
                raise ValueError("primary prediction artifact contains a non-probe row")
            key = _event_key(row)
            if key in keys:
                raise ValueError(f"duplicate primary prediction key: {key}")
            keys.add(key)
            for field in (
                "predicted_response_probability",
                "estimated_item_prerequisite_state",
            ):
                values = row[field]
                if set(values) != set(CORE_REPRESENTATIONS):
                    raise ValueError(f"primary prediction {field} conditions changed")
                if any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                    or not 0.0 <= float(value) <= 1.0
                    for value in values.values()
                ):
                    raise ValueError(f"primary prediction {field} is not probabilistic")
            rows.append(row)
    if not rows:
        raise ValueError("primary public-prediction artifact is empty")
    return rows


def paired_whole_learner_bootstrap(
    learner_ids: Sequence[str],
    oracle_values: Sequence[float] | np.ndarray,
    reference_estimates: Sequence[float] | np.ndarray,
    candidate_estimates: Sequence[float] | np.ndarray,
    *,
    repeats: int = BOOTSTRAP_REPEATS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Recompute paired candidate-minus-reference RMSE/MAE by learner."""

    if repeats < 1:
        raise ValueError("bootstrap repeats must be positive")
    learner = np.asarray([str(value) for value in learner_ids], dtype=object)
    oracle = np.asarray(oracle_values, dtype=float)
    reference = np.asarray(reference_estimates, dtype=float)
    candidate = np.asarray(candidate_estimates, dtype=float)
    if not (
        learner.ndim == oracle.ndim == reference.ndim == candidate.ndim == 1
        and len(learner) == len(oracle) == len(reference) == len(candidate)
        and len(learner) > 0
    ):
        raise ValueError("paired bootstrap inputs must be nonempty paired vectors")
    for name, values in (
        ("oracle", oracle),
        ("reference", reference),
        ("candidate", candidate),
    ):
        if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 1.0):
            raise ValueError(f"{name} values must be finite and lie in [0, 1]")
    learners = sorted(set(learner.tolist()))
    learner_index = {learner_id: index for index, learner_id in enumerate(learners)}
    event_learner_index = np.asarray(
        [learner_index[str(learner_id)] for learner_id in learner], dtype=int
    )
    counts = np.bincount(event_learner_index, minlength=len(learners)).astype(float)
    if np.any(counts == 0):
        raise ValueError("bootstrap learner indexing produced an empty learner")
    reference_squared = (reference - oracle) ** 2
    candidate_squared = (candidate - oracle) ** 2
    reference_absolute = np.abs(reference - oracle)
    candidate_absolute = np.abs(candidate - oracle)

    def learner_sums(values: np.ndarray) -> np.ndarray:
        return np.bincount(
            event_learner_index, weights=values, minlength=len(learners)
        )

    reference_squared_sums = learner_sums(reference_squared)
    candidate_squared_sums = learner_sums(candidate_squared)
    reference_absolute_sums = learner_sums(reference_absolute)
    candidate_absolute_sums = learner_sums(candidate_absolute)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(
        0, len(learners), size=(repeats, len(learners)), dtype=np.int32
    )
    denominators = counts[sampled].sum(axis=1)
    reference_rmse_draws = np.sqrt(
        reference_squared_sums[sampled].sum(axis=1) / denominators
    )
    candidate_rmse_draws = np.sqrt(
        candidate_squared_sums[sampled].sum(axis=1) / denominators
    )
    reference_mae_draws = (
        reference_absolute_sums[sampled].sum(axis=1) / denominators
    )
    candidate_mae_draws = candidate_absolute_sums[sampled].sum(axis=1) / denominators
    delta_rmse_draws = candidate_rmse_draws - reference_rmse_draws
    delta_mae_draws = candidate_mae_draws - reference_mae_draws

    def summarize(
        reference_point: float, candidate_point: float, draws: np.ndarray
    ) -> dict[str, Any]:
        interval = [
            float(np.quantile(draws, 0.025, method="linear")),
            float(np.quantile(draws, 0.975, method="linear")),
        ]
        crosses = interval[0] <= 0.0 <= interval[1]
        if crosses:
            relation = "crosses_zero"
        elif interval[0] > 0.0:
            relation = "entirely_above_zero"
        else:
            relation = "entirely_below_zero"
        return {
            "reference_kstar": reference_point,
            "candidate": candidate_point,
            "candidate_minus_kstar": candidate_point - reference_point,
            "percentile_interval_95": interval,
            "interval_crosses_zero": crosses,
            "interval_relation_to_zero": relation,
        }

    return {
        "learners": len(learners),
        "events": len(oracle),
        "events_per_learner_minimum": int(np.min(counts)),
        "events_per_learner_maximum": int(np.max(counts)),
        "repeats": repeats,
        "seed": seed,
        "sampling_unit": "whole learner",
        "aggregation": "event_weighted",
        "sign_convention": "candidate minus K*; positive favors K*",
        "rmse": summarize(
            float(np.sqrt(np.mean(reference_squared))),
            float(np.sqrt(np.mean(candidate_squared))),
            delta_rmse_draws,
        ),
        "mae": summarize(
            float(np.mean(reference_absolute)),
            float(np.mean(candidate_absolute)),
            delta_mae_draws,
        ),
    }


def _bootstrap_comparisons(
    prediction_rows: Sequence[Mapping[str, Any]],
    oracle_targets: Mapping[tuple[str, int], float],
    *,
    repeats: int,
    seed: int,
) -> dict[str, Any]:
    regimes = np.asarray([str(row["grammar_regime"]) for row in prediction_rows])
    keys = [_event_key(row) for row in prediction_rows]
    learner_ids = np.asarray([key[0] for key in keys], dtype=object)
    oracle = np.asarray([oracle_targets[key] for key in keys], dtype=float)
    estimates = {
        representation_id: np.asarray(
            [
                float(row["estimated_item_prerequisite_state"][representation_id])
                for row in prediction_rows
            ],
            dtype=float,
        )
        for representation_id in CORE_REPRESENTATIONS
    }
    masks = {
        "all_probe": np.ones(len(prediction_rows), dtype=bool),
        **{regime: regimes == regime for regime in GRAMMAR_REGIMES},
    }
    full_learner_set = set(learner_ids.tolist())
    for regime, selected in masks.items():
        if set(learner_ids[selected].tolist()) != full_learner_set:
            raise ValueError(f"regime {regime} does not contain every learner")
    output: dict[str, Any] = {}
    for candidate_id in CANDIDATE_IDS:
        output[candidate_id] = {
            "display_label": REPRESENTATION_LABELS[candidate_id],
            "reference_id": REFERENCE_ID,
            "candidate_minus_kstar_by_regime": {
                regime: paired_whole_learner_bootstrap(
                    learner_ids[selected],
                    oracle[selected],
                    estimates[REFERENCE_ID][selected],
                    estimates[candidate_id][selected],
                    repeats=repeats,
                    seed=seed,
                )
                for regime, selected in masks.items()
            },
        }
    return output


def run_study(dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    plan, _primary_plan, primary_result = _validate_plan(dataset_dir, output_dir)
    prediction_path = output_dir / "observable_probe_state_estimates.jsonl.gz"
    prediction_rows = load_public_prediction_rows(prediction_path)
    events = load_observable_events(dataset_dir / "interactions.jsonl.gz")
    if set(_event_key(row) for row in prediction_rows) != {
        _event_key(event) for event in events if event["phase"] == "probe"
    }:
        raise ValueError("primary predictions differ from public terminal-probe keys")
    oracle_declared = plan["private_oracle_declared_in_manifest"]
    oracle_path = dataset_dir / str(oracle_declared["path"])
    oracle_actual_sha256 = file_sha256(oracle_path)
    if oracle_actual_sha256 != oracle_declared["sha256"]:
        raise ValueError("private oracle hash differs from the frozen manifest")
    oracle_targets, join_audit = _strict_oracle_probe_join_after_predictions(
        oracle_path,
        events,
        prediction_rows,
        prediction_artifact_path=prediction_path,
        prediction_artifact_sha256=primary_result["observable_prediction_artifact"][
            "sha256"
        ],
    )
    comparisons = _bootstrap_comparisons(
        prediction_rows,
        oracle_targets,
        repeats=int(plan["method"]["repeats"]),
        seed=int(plan["method"]["seed"]),
    )
    result = {
        "study_id": ROBUSTNESS_STUDY_ID,
        "status": "FINAL_POST_PLAN_ROBUSTNESS_RESULT",
        "post_plan_classification": (
            "User-requested after the frozen primary result; not preregistered "
            "primary inference."
        ),
        "primary_plan_or_result_modified": False,
        "post_plan_specification_sha256": file_sha256(
            output_dir / "post_plan_bootstrap_plan.json"
        ),
        "primary_result_sha256": file_sha256(output_dir / "results.json"),
        "public_prediction_sha256": file_sha256(prediction_path),
        "private_oracle_sha256": oracle_actual_sha256,
        "same_probe_event_key_sha256_as_primary": (
            _event_key_sha256(_event_key(row) for row in prediction_rows)
            == primary_result["join_audit"]["probe_event_key_sha256"]
        ),
        "join_audit": join_audit,
        "method": plan["method"],
        "comparisons_by_candidate": comparisons,
        "interpretation_boundary": (
            "Intervals quantify resampling uncertainty across the 1,000 synthetic "
            "learners for item-level prerequisite-state error differences; they do "
            "not establish human KC or mastery truth."
        ),
    }
    if not result["same_probe_event_key_sha256_as_primary"]:
        raise ValueError("bootstrap probe keys differ from the primary study")
    result_path = output_dir / "post_plan_paired_bootstrap.json"
    _write_frozen_json(result_path, result, "post-plan paired-bootstrap result")
    artifact_manifest = {
        "study_id": ROBUSTNESS_STUDY_ID,
        "classification": "post-plan robustness",
        "artifacts": {
            path.name: {
                "sha256": file_sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (
                output_dir / "post_plan_bootstrap_plan.json",
                result_path,
            )
        },
    }
    _write_frozen_json(
        output_dir / "post_plan_bootstrap_artifact_manifest.json",
        artifact_manifest,
        "post-plan bootstrap artifact manifest",
    )
    print(f"wrote {result_path}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("plan", "run"), required=True)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    dataset_dir = args.dataset_dir.resolve()
    output_dir = args.output_dir.resolve()
    if args.stage == "plan":
        create_plan(dataset_dir, output_dir)
        print(
            f"locked explicitly post-plan robustness specification at {output_dir}",
            flush=True,
        )
        return 0
    run_study(dataset_dir, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
