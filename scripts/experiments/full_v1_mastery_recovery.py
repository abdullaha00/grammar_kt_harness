#!/usr/bin/env python3
"""Run a leakage-bounded terminal-probe prerequisite-state recovery study.

The study reuses five frozen RQ2 item-to-KC projections and the exact RQ2
observable-history logistic predictor.  It first materialises response
probabilities and inverse-link item prerequisite-state estimates using public
events only.  The private learner oracle is opened only after that artifact is
frozen, and is then used solely to evaluate against ``aggregated_mastery_before``.

The estimated quantity is an item-level prerequisite state under the declared
synthetic response link.  It is not a logistic coefficient, an estimate of an
individual KC, or a claim about human mastery.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.experiments.rq2_kc_misspecification import (
    file_sha256,
    fit_observable_logistic,
    load_observable_events,
    load_projection_bundle,
)


DEFAULT_DATASET = ROOT / "data/grammar_kt_full_v1"
DEFAULT_RQ2_DIR = ROOT / "reports/full_v1_artifacts/rq2_misspecification_v1"
DEFAULT_OUTPUT = ROOT / "reports/full_v1_artifacts/mastery_recovery_v1"
STUDY_ID = "full_v1_terminal_probe_prerequisite_state_recovery_v1"

CORE_REPRESENTATIONS = (
    "true_kstar",
    "coarse_linguistic_families",
    "structural_split2",
    "structural_split4",
    "exact_cell",
)
REPRESENTATION_LABELS = {
    "true_kstar": "K*",
    "coarse_linguistic_families": "coarse",
    "structural_split2": "split2",
    "structural_split4": "split4",
    "exact_cell": "exact-cell",
}
GRAMMAR_REGIMES = ("seen", "unseen_combination", "unseen_value")
CALIBRATION_BINS = 10

ORACLE_SCHEMA = {
    "learner_id",
    "item_id",
    "sequence_index",
    "phase",
    "pass_index",
    "grammar_regime",
    "active_generator_kc_ids",
    "mastery_before",
    "aggregated_mastery_before",
    "response_probability",
    "response_draw",
    "correct",
    "updates_mastery",
    "mastery_after",
}
PAIR_FIELDS = (
    "item_id",
    "phase",
    "pass_index",
    "grammar_regime",
    "correct",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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


def _write_frozen_json(path: Path, value: Any, label: str) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    _write_frozen_bytes(path, payload.encode("utf-8"), label)


def _write_frozen_bytes(path: Path, payload: bytes, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise FileExistsError(f"refusing to overwrite changed {label}: {path}")
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _deterministic_gzip(payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0
    ) as stream:
        stream.write(payload)
    return buffer.getvalue()


def _event_key(row: Mapping[str, Any]) -> tuple[str, int]:
    return str(row["learner_id"]), int(row["sequence_index"])


def _event_key_sha256(keys: Iterable[tuple[str, int]]) -> str:
    payload = "".join(_canonical_json(list(key)) + "\n" for key in sorted(keys))
    return _sha256_bytes(payload.encode("utf-8"))


def _read_manifest(dataset_dir: Path) -> dict[str, Any]:
    path = dataset_dir / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("dataset_id") != "grammar_kt_full_v1":
        raise ValueError("mastery recovery requires grammar_kt_full_v1")
    if manifest.get("status") != "FROZEN_BASELINE_COMPLETE":
        raise ValueError("mastery recovery requires a frozen full-v1 baseline")
    return manifest


def _declared_oracle(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Read oracle metadata from the public manifest, not from oracle bytes."""

    relative_path = str(manifest["scientific_layers"]["private_oracle"])
    artifact = manifest["simulation"]["stream_summary"]["artifacts"][
        "private_oracle"
    ]
    return {
        "path": relative_path,
        "sha256": str(artifact["sha256"]),
        "content_sha256": str(artifact["content_sha256"]),
        "rows": int(artifact["rows"]),
    }


def _load_and_validate_rq2(
    rq2_dir: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, tuple[str, ...]]]]:
    plan_path = rq2_dir / "study_plan.json"
    projection_path = rq2_dir / "projections.jsonl"
    if not plan_path.is_file() or not projection_path.is_file():
        raise FileNotFoundError("frozen RQ2 plan and projection bundle are required")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("study_id") != "full_v1_rq2_kc_misspecification_v1":
        raise ValueError("unexpected RQ2 study ID")
    if plan.get("status") != "PREREGISTERED_BEFORE_OUTCOME_ANALYSIS":
        raise ValueError("RQ2 plan is not the frozen preregistered plan")
    if plan["projection_bundle"]["sha256"] != file_sha256(projection_path):
        raise ValueError("frozen RQ2 projection bundle hash mismatch")
    rq2_script = ROOT / str(plan["implementation"]["script"])
    if plan["implementation"]["script_sha256"] != file_sha256(rq2_script):
        raise ValueError("RQ2 predictor implementation changed after its plan")
    if not set(CORE_REPRESENTATIONS).issubset(
        set(plan["conditions_in_execution_order"])
    ):
        raise ValueError("frozen RQ2 plan lacks a requested core representation")
    all_projections = load_projection_bundle(projection_path)
    projections = {
        representation_id: all_projections[representation_id]
        for representation_id in CORE_REPRESENTATIONS
    }
    item_sets = [set(projection) for projection in projections.values()]
    if not item_sets or any(items != item_sets[0] for items in item_sets[1:]):
        raise ValueError("core RQ2 projections do not cover identical item sets")
    if any(any(not active for active in projection.values()) for projection in projections.values()):
        raise ValueError("a core RQ2 projection contains an empty item mapping")
    return plan, projections


def inverse_response_link(
    probabilities: Sequence[float] | np.ndarray,
    *,
    guess: float,
    slip: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Map response probabilities to derived item prerequisite states."""

    if not math.isfinite(guess) or not math.isfinite(slip):
        raise ValueError("guess and slip must be finite")
    scale = 1.0 - guess - slip
    if guess < 0.0 or slip < 0.0 or scale <= 0.0:
        raise ValueError("guess/slip must be non-negative and sum to less than one")
    probability = np.asarray(probabilities, dtype=float)
    if probability.ndim != 1 or not np.all(np.isfinite(probability)):
        raise ValueError("response probabilities must be a finite vector")
    if np.any(probability < 0.0) or np.any(probability > 1.0):
        raise ValueError("response probabilities must lie in [0, 1]")
    raw = (probability - guess) / scale
    estimate = np.clip(raw, 0.0, 1.0)
    return estimate, {
        "response_probability_minimum": float(np.min(probability))
        if len(probability)
        else None,
        "response_probability_maximum": float(np.max(probability))
        if len(probability)
        else None,
        "unclipped_state_minimum": float(np.min(raw)) if len(raw) else None,
        "unclipped_state_maximum": float(np.max(raw)) if len(raw) else None,
        "clipped_below_zero": int(np.sum(raw < 0.0)),
        "clipped_above_one": int(np.sum(raw > 1.0)),
        "estimated_state_minimum": float(np.min(estimate)) if len(estimate) else None,
        "estimated_state_maximum": float(np.max(estimate)) if len(estimate) else None,
    }


def _calibration_metrics(
    oracle: np.ndarray, estimate: np.ndarray, *, bins: int
) -> dict[str, Any]:
    if bins < 2:
        raise ValueError("calibration requires at least two bins")
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, Any]] = []
    weighted_absolute_gap = 0.0
    maximum_absolute_gap = 0.0
    for index in range(bins):
        selected = (estimate >= edges[index]) & (
            estimate <= edges[index + 1]
            if index == bins - 1
            else estimate < edges[index + 1]
        )
        count = int(np.sum(selected))
        if count:
            estimate_mean = float(np.mean(estimate[selected]))
            oracle_mean = float(np.mean(oracle[selected]))
            gap = estimate_mean - oracle_mean
            absolute_gap = abs(gap)
            weighted_absolute_gap += (count / len(estimate)) * absolute_gap
            maximum_absolute_gap = max(maximum_absolute_gap, absolute_gap)
        else:
            estimate_mean = None
            oracle_mean = None
            gap = None
        rows.append(
            {
                "bin_index": index + 1,
                "lower_inclusive": float(edges[index]),
                "upper_inclusive_only_for_last_bin": float(edges[index + 1]),
                "n": count,
                "mean_estimated_item_prerequisite_state": estimate_mean,
                "mean_oracle_aggregated_mastery_before": oracle_mean,
                "estimate_minus_oracle": gap,
            }
        )
    variance = float(np.var(estimate))
    if variance > 0.0:
        slope = float(
            np.mean((estimate - np.mean(estimate)) * (oracle - np.mean(oracle)))
            / variance
        )
        intercept = float(np.mean(oracle) - slope * np.mean(estimate))
    else:
        slope = None
        intercept = None
    return {
        "definition": (
            "Calibration compares the derived item prerequisite-state estimate "
            "with oracle aggregated_mastery_before in ten fixed-width estimate bins."
        ),
        "bins": bins,
        "mean_estimate_minus_oracle": float(np.mean(estimate - oracle)),
        "fixed_bin_expected_absolute_gap": float(weighted_absolute_gap),
        "maximum_nonempty_bin_absolute_gap": float(maximum_absolute_gap),
        "linear_truth_on_estimate_intercept": intercept,
        "linear_truth_on_estimate_slope": slope,
        "bin_table": rows,
    }


def recovery_metrics(
    oracle_values: Sequence[float] | np.ndarray,
    estimates: Sequence[float] | np.ndarray,
    *,
    bins: int = CALIBRATION_BINS,
) -> dict[str, Any]:
    oracle = np.asarray(oracle_values, dtype=float)
    estimate = np.asarray(estimates, dtype=float)
    if oracle.ndim != 1 or estimate.ndim != 1 or len(oracle) != len(estimate):
        raise ValueError("oracle and estimates must be exactly paired vectors")
    if not len(oracle):
        return {
            "n": 0,
            "rmse": None,
            "mae": None,
            "pearson_correlation": None,
            "calibration": None,
        }
    if not np.all(np.isfinite(oracle)) or not np.all(np.isfinite(estimate)):
        raise ValueError("oracle and estimates must be finite")
    if (
        np.any(oracle < 0.0)
        or np.any(oracle > 1.0)
        or np.any(estimate < 0.0)
        or np.any(estimate > 1.0)
    ):
        raise ValueError("oracle and estimates must lie in [0, 1]")
    difference = estimate - oracle
    if len(oracle) >= 2 and float(np.std(oracle)) > 0.0 and float(np.std(estimate)) > 0.0:
        correlation = float(np.corrcoef(estimate, oracle)[0, 1])
    else:
        correlation = None
    return {
        "n": len(oracle),
        "rmse": float(np.sqrt(np.mean(difference**2))),
        "mae": float(np.mean(np.abs(difference))),
        "pearson_correlation": correlation,
        "calibration": _calibration_metrics(oracle, estimate, bins=bins),
    }


def _public_input_record(dataset_dir: Path, rq2_dir: Path) -> dict[str, Any]:
    paths = {
        "dataset_manifest": dataset_dir / "manifest.json",
        "observable_interactions": dataset_dir / "interactions.jsonl.gz",
        "rq2_study_plan": rq2_dir / "study_plan.json",
        "rq2_projection_bundle": rq2_dir / "projections.jsonl",
    }
    return {
        name: {
            "path": str(path.relative_to(ROOT)),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for name, path in paths.items()
    }


def create_plan(dataset_dir: Path, rq2_dir: Path, output_dir: Path) -> dict[str, Any]:
    manifest = _read_manifest(dataset_dir)
    rq2_plan, projections = _load_and_validate_rq2(rq2_dir)
    condition_model_seed = int(rq2_plan["model"]["random_seed"])
    condition = manifest["simulation"]["pilot"]["condition"]
    guess = float(condition["guess"])
    slip = float(condition["slip"])
    if guess != 0.1 or slip != 0.1:
        raise ValueError("full-v1 declared response link is not guess=.1/slip=.1")
    script_path = Path(__file__).resolve()
    plan = {
        "study_id": STUDY_ID,
        "status": "LOCKED_BEFORE_PRIVATE_ORACLE_READ",
        "dataset_scope": "frozen grammar_kt_full_v1, all 1000 learners",
        "research_question": (
            "How accurately do observable RQ2 terminal-probe response predictions, "
            "after inversion of the declared synthetic response link, recover the "
            "oracle item prerequisite state?"
        ),
        "conditions_in_execution_order": list(CORE_REPRESENTATIONS),
        "condition_labels": REPRESENTATION_LABELS,
        "frozen_rq2_reuse": {
            "projection_source": str(
                (rq2_dir / "projections.jsonl").relative_to(ROOT)
            ),
            "predictor_implementation": rq2_plan["implementation"]["script"],
            "predictor_implementation_sha256": rq2_plan["implementation"][
                "script_sha256"
            ],
            "predictor_name": rq2_plan["model"]["name"],
            "model_random_seed": condition_model_seed,
            "core_projection_counts": {
                representation_id: {
                    "items": len(projection),
                    "hypothesis_kcs": len(
                        {kc_id for active in projection.values() for kc_id in active}
                    ),
                }
                for representation_id, projection in projections.items()
            },
        },
        "estimator": {
            "name": "derived_terminal_probe_item_prerequisite_state",
            "input": "public-only fitted terminal-probe response probability p_hat",
            "formula": "clip((p_hat - 0.1) / 0.8, 0, 1)",
            "response_link": {
                "guess": guess,
                "slip": slip,
                "scale": 1.0 - guess - slip,
                "generator_formula": "p = guess + (1 - guess - slip) * aggregated_mastery_before",
            },
            "target_loaded_only_during_evaluation": "oracle aggregated_mastery_before",
            "scope_warning": (
                "This is a derived item-level weakest-prerequisite state estimate. "
                "It is not a logistic coefficient, a recovered individual KC state, "
                "or human mastery."
            ),
        },
        "evaluation": {
            "events": "terminal non-updating probes only",
            "regimes": ["all_probe", *GRAMMAR_REGIMES],
            "metrics": [
                "RMSE",
                "MAE",
                "Pearson correlation",
                "10-bin fixed-width state calibration",
            ],
            "calibration_outputs": [
                "signed mean estimate-minus-oracle bias",
                "expected absolute bin gap",
                "maximum nonempty-bin absolute gap",
                "truth-on-estimate linear intercept and slope",
                "bin table",
            ],
            "join_key": ["learner_id", "sequence_index"],
            "paired_fields_checked": list(PAIR_FIELDS),
        },
        "leakage_controls": {
            "oracle_read_during_plan": False,
            "oracle_read_during_prediction_fit": False,
            "public_predictions_frozen_before_oracle_open": True,
            "oracle_use": "evaluation target and strict join validation only",
            "oracle_fit_tuning_or_condition_selection": False,
            "probe_outcomes_used_for_fit_or_tuning": False,
            "same_probe_keys_and_oracle_targets_for_every_representation": True,
        },
        "public_inputs": _public_input_record(dataset_dir, rq2_dir),
        "private_oracle_declared_but_not_opened": _declared_oracle(manifest),
        "implementation": {
            "script": str(script_path.relative_to(ROOT)),
            "script_sha256": file_sha256(script_path),
            "repository_head_at_plan": _repository_head(),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
        },
        "exact_commands": {
            "plan": ".venv/bin/python scripts/experiments/full_v1_mastery_recovery.py --stage plan",
            "run": ".venv/bin/python scripts/experiments/full_v1_mastery_recovery.py --stage run",
            "test": ".venv/bin/python -m pytest -q tests/test_full_v1_mastery_recovery.py",
        },
        "optional_bkt_sensitivity": {
            "run": False,
            "reason": (
                "The bounded primary study avoids conflating BKT's correctness-conditioned "
                "Bayesian KC state with the generator's outcome-independent opportunity update."
            ),
        },
    }
    _write_frozen_json(output_dir / "study_plan.json", plan, "study plan")
    return plan


def _validate_plan(
    dataset_dir: Path, rq2_dir: Path, output_dir: Path
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, tuple[str, ...]]],
]:
    plan_path = output_dir / "study_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError("run requires study_plan.json from --stage plan")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("study_id") != STUDY_ID:
        raise ValueError("study plan ID does not match this implementation")
    if plan.get("status") != "LOCKED_BEFORE_PRIVATE_ORACLE_READ":
        raise ValueError("study plan was not locked before private-oracle evaluation")
    if plan["implementation"]["script_sha256"] != file_sha256(Path(__file__).resolve()):
        raise ValueError("mastery-recovery implementation changed after planning")
    if plan["public_inputs"] != _public_input_record(dataset_dir, rq2_dir):
        raise ValueError("public inputs changed after planning")
    manifest = _read_manifest(dataset_dir)
    if plan["private_oracle_declared_but_not_opened"] != _declared_oracle(manifest):
        raise ValueError("manifest-declared oracle metadata changed after planning")
    rq2_plan, projections = _load_and_validate_rq2(rq2_dir)
    if plan["conditions_in_execution_order"] != list(CORE_REPRESENTATIONS):
        raise ValueError("planned core representation order changed")
    if plan["frozen_rq2_reuse"]["model_random_seed"] != int(
        rq2_plan["model"]["random_seed"]
    ):
        raise ValueError("RQ2 model seed differs from the locked recovery plan")
    return plan, manifest, projections


def _build_public_estimates(
    events: Sequence[dict[str, Any]],
    projections: Mapping[str, Mapping[str, Sequence[str]]],
    *,
    guess: float,
    slip: float,
    model_seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    evaluation_events = [event for event in events if event["phase"] == "probe"]
    if not evaluation_events:
        raise ValueError("no terminal probe events found")
    evaluation_keys = [_event_key(event) for event in evaluation_events]
    if len(evaluation_keys) != len(set(evaluation_keys)):
        raise ValueError("public terminal probes have duplicate join keys")
    probabilities: dict[str, np.ndarray] = {}
    estimates: dict[str, np.ndarray] = {}
    audits: dict[str, Any] = {}
    for representation_id in CORE_REPRESENTATIONS:
        print(f"fit public-only RQ2 predictor: {representation_id}", flush=True)
        probability, model_audit = fit_observable_logistic(
            events,
            dict(projections[representation_id]),
            random_seed=model_seed,
        )
        if len(probability) != len(evaluation_events):
            raise ValueError("RQ2 prediction count does not match terminal probes")
        estimate, inverse_audit = inverse_response_link(
            probability, guess=guess, slip=slip
        )
        probabilities[representation_id] = probability
        estimates[representation_id] = estimate
        audits[representation_id] = {
            "model": model_audit,
            "inverse_link": inverse_audit,
        }
    rows: list[dict[str, Any]] = []
    for index, event in enumerate(evaluation_events):
        rows.append(
            {
                "learner_id": str(event["learner_id"]),
                "sequence_index": int(event["sequence_index"]),
                "item_id": str(event["item_id"]),
                "phase": "probe",
                "pass_index": int(event["pass_index"]),
                "grammar_regime": str(event["grammar_regime"]),
                "predicted_response_probability": {
                    representation_id: float(probabilities[representation_id][index])
                    for representation_id in CORE_REPRESENTATIONS
                },
                "estimated_item_prerequisite_state": {
                    representation_id: float(estimates[representation_id][index])
                    for representation_id in CORE_REPRESENTATIONS
                },
            }
        )
    return rows, audits


def _render_public_estimates(rows: Sequence[Mapping[str, Any]]) -> bytes:
    payload = "".join(_canonical_json(row) + "\n" for row in rows).encode("utf-8")
    return _deterministic_gzip(payload)


def _strict_oracle_probe_join_after_predictions(
    oracle_path: Path,
    public_events: Sequence[Mapping[str, Any]],
    prediction_rows: Sequence[Mapping[str, Any]],
    *,
    prediction_artifact_path: Path,
    prediction_artifact_sha256: str,
) -> tuple[dict[tuple[str, int], float], dict[str, Any]]:
    """Open oracle only after verifying the public prediction artifact exists."""

    if not prediction_artifact_path.is_file():
        raise FileNotFoundError("public prediction artifact must exist before oracle open")
    if file_sha256(prediction_artifact_path) != prediction_artifact_sha256:
        raise ValueError("public prediction artifact changed before oracle evaluation")
    public_by_key: dict[tuple[str, int], Mapping[str, Any]] = {}
    for event in public_events:
        key = _event_key(event)
        if key in public_by_key:
            raise ValueError(f"duplicate public event join key: {key}")
        public_by_key[key] = event
    prediction_keys = [_event_key(row) for row in prediction_rows]
    if len(prediction_keys) != len(set(prediction_keys)):
        raise ValueError("duplicate prediction join key")
    oracle_keys: set[tuple[str, int]] = set()
    probe_targets: dict[tuple[str, int], float] = {}
    with gzip.open(oracle_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if set(row) != ORACLE_SCHEMA:
                raise ValueError("private-oracle schema changed")
            key = _event_key(row)
            if key in oracle_keys:
                raise ValueError(f"duplicate oracle event join key: {key}")
            oracle_keys.add(key)
            public = public_by_key.get(key)
            if public is None:
                raise ValueError(f"oracle join key absent from public events: {key}")
            for field in PAIR_FIELDS:
                if row[field] != public[field]:
                    raise ValueError(f"oracle/public mismatch at {key} for {field}")
            if row["phase"] == "probe":
                value = row["aggregated_mastery_before"]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("oracle aggregated mastery must be numeric")
                target = float(value)
                if not math.isfinite(target) or not 0.0 <= target <= 1.0:
                    raise ValueError("oracle aggregated mastery must lie in [0, 1]")
                probe_targets[key] = target
    if oracle_keys != set(public_by_key):
        missing = len(set(public_by_key) - oracle_keys)
        extra = len(oracle_keys - set(public_by_key))
        raise ValueError(
            f"oracle/public event-key sets differ: missing={missing}, extra={extra}"
        )
    if set(prediction_keys) != set(probe_targets):
        missing = len(set(prediction_keys) - set(probe_targets))
        extra = len(set(probe_targets) - set(prediction_keys))
        raise ValueError(
            f"prediction/oracle probe-key sets differ: missing={missing}, extra={extra}"
        )
    return probe_targets, {
        "join_key": ["learner_id", "sequence_index"],
        "paired_fields_checked": list(PAIR_FIELDS),
        "public_events": len(public_by_key),
        "oracle_events": len(oracle_keys),
        "terminal_probe_predictions": len(prediction_keys),
        "terminal_probe_oracle_targets": len(probe_targets),
        "all_public_oracle_keys_match": True,
        "all_probe_prediction_oracle_keys_match": True,
        "public_event_key_sha256": _event_key_sha256(public_by_key),
        "probe_event_key_sha256": _event_key_sha256(prediction_keys),
    }


def _evaluate(
    prediction_rows: Sequence[Mapping[str, Any]],
    oracle_targets: Mapping[tuple[str, int], float],
) -> dict[str, Any]:
    regimes = [str(row["grammar_regime"]) for row in prediction_rows]
    unknown = set(regimes) - set(GRAMMAR_REGIMES)
    if unknown:
        raise ValueError(f"unknown terminal-probe grammar regimes: {sorted(unknown)}")
    keys = [_event_key(row) for row in prediction_rows]
    oracle = np.asarray([oracle_targets[key] for key in keys], dtype=float)
    output: dict[str, Any] = {}
    for representation_id in CORE_REPRESENTATIONS:
        estimate = np.asarray(
            [
                float(row["estimated_item_prerequisite_state"][representation_id])
                for row in prediction_rows
            ],
            dtype=float,
        )
        metrics: dict[str, Any] = {
            "all_probe": recovery_metrics(oracle, estimate)
        }
        regime_array = np.asarray(regimes)
        for regime in GRAMMAR_REGIMES:
            selected = regime_array == regime
            if not np.any(selected):
                raise ValueError(f"terminal probes lack planned regime: {regime}")
            metrics[regime] = recovery_metrics(oracle[selected], estimate[selected])
        output[representation_id] = {
            "display_label": REPRESENTATION_LABELS[representation_id],
            "metrics_by_regime": metrics,
        }
    return output


def run_study(dataset_dir: Path, rq2_dir: Path, output_dir: Path) -> dict[str, Any]:
    plan, manifest, projections = _validate_plan(dataset_dir, rq2_dir, output_dir)
    events = load_observable_events(dataset_dir / "interactions.jsonl.gz")
    learners = {str(event["learner_id"]) for event in events}
    if len(learners) != int(manifest["scale"]["learners"]):
        raise ValueError("public event stream does not contain every full-v1 learner")
    if len(events) != int(manifest["scale"]["interactions"]):
        raise ValueError("public event stream does not contain every full-v1 event")
    expected_items = next(iter(projections.values())).keys()
    if {str(event["item_id"]) for event in events} != set(expected_items):
        raise ValueError("public events and frozen RQ2 projections differ on item set")
    response_link = plan["estimator"]["response_link"]
    prediction_rows, model_audits = _build_public_estimates(
        events,
        projections,
        guess=float(response_link["guess"]),
        slip=float(response_link["slip"]),
        model_seed=int(plan["frozen_rq2_reuse"]["model_random_seed"]),
    )
    prediction_path = output_dir / "observable_probe_state_estimates.jsonl.gz"
    prediction_payload = _render_public_estimates(prediction_rows)
    _write_frozen_bytes(
        prediction_path,
        prediction_payload,
        "public-only terminal-probe estimates",
    )
    prediction_sha256 = file_sha256(prediction_path)
    print(
        f"froze public-only estimates before oracle access: {prediction_path}",
        flush=True,
    )

    # This is the first access to private-oracle bytes in the plan/run workflow.
    oracle_declared = plan["private_oracle_declared_but_not_opened"]
    oracle_path = dataset_dir / str(oracle_declared["path"])
    oracle_actual_sha256 = file_sha256(oracle_path)
    if oracle_actual_sha256 != oracle_declared["sha256"]:
        raise ValueError("private oracle differs from the hash declared in the manifest")
    oracle_targets, join_audit = _strict_oracle_probe_join_after_predictions(
        oracle_path,
        events,
        prediction_rows,
        prediction_artifact_path=prediction_path,
        prediction_artifact_sha256=prediction_sha256,
    )
    if join_audit["oracle_events"] != int(oracle_declared["rows"]):
        raise ValueError("private oracle row count differs from its manifest declaration")
    metrics = _evaluate(prediction_rows, oracle_targets)
    probe_events = sum(event["phase"] == "probe" for event in events)
    expected_probe_events = int(
        manifest["simulation"]["stream_summary"]["phase_counts"]["probe"]
    )
    if probe_events != expected_probe_events or len(prediction_rows) != expected_probe_events:
        raise ValueError("terminal-probe count differs from the frozen manifest")
    result = {
        "study_id": STUDY_ID,
        "status": "FINAL_FULL_DATASET_ORACLE_EVALUATION",
        "plan_sha256": file_sha256(output_dir / "study_plan.json"),
        "frozen_rq2_projection_bundle_sha256": file_sha256(
            rq2_dir / "projections.jsonl"
        ),
        "observable_prediction_artifact": {
            "path": prediction_path.name,
            "sha256": prediction_sha256,
            "bytes": prediction_path.stat().st_size,
            "rows": len(prediction_rows),
            "contains_private_oracle_fields": False,
            "frozen_before_private_oracle_open": True,
        },
        "private_oracle_evaluation": {
            "path": str(oracle_declared["path"]),
            "declared_sha256": oracle_declared["sha256"],
            "actual_sha256_after_predictions_frozen": oracle_actual_sha256,
            "fit_tuning_or_condition_selection": False,
            "target_field": "aggregated_mastery_before",
        },
        "scale": {
            "learners": len(learners),
            "public_events": len(events),
            "acquisition_events": len(events) - probe_events,
            "terminal_probe_events": probe_events,
        },
        "join_audit": join_audit,
        "model_and_inverse_link_audit": model_audits,
        "metrics_by_representation": metrics,
        "quantity_definition": {
            "estimate": "derived terminal-probe item prerequisite state",
            "target": (
                "oracle aggregated_mastery_before: the minimum pre-response mastery "
                "over the item's active generator KCs"
            ),
            "not_claimed": [
                "logistic coefficient recovery",
                "individual generator-KC mastery recovery",
                "human learner mastery",
            ],
        },
        "interpretation_boundary": (
            "Results quantify item-level weakest-prerequisite-state recovery only "
            "inside the declared frozen synthetic world."
        ),
    }
    result_path = output_dir / "results.json"
    _write_frozen_json(result_path, result, "mastery-recovery result")
    artifact_manifest = {
        "study_id": STUDY_ID,
        "artifacts": {
            path.name: {
                "sha256": file_sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (
                output_dir / "study_plan.json",
                prediction_path,
                result_path,
            )
        },
    }
    _write_frozen_json(
        output_dir / "artifact_manifest.json",
        artifact_manifest,
        "artifact manifest",
    )
    print(f"wrote {result_path}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("plan", "run"), required=True)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--rq2-dir", type=Path, default=DEFAULT_RQ2_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    dataset_dir = args.dataset_dir.resolve()
    rq2_dir = args.rq2_dir.resolve()
    output_dir = args.output_dir.resolve()
    if args.stage == "plan":
        plan = create_plan(dataset_dir, rq2_dir, output_dir)
        print(
            f"locked {len(plan['conditions_in_execution_order'])} core conditions "
            f"before private-oracle access at {output_dir}",
            flush=True,
        )
        return 0
    run_study(dataset_dir, rq2_dir, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
