#!/usr/bin/env python3
"""Secondary fixed-BKT terminal KC-state recovery on frozen full-v1.

This deliberately misspecified secondary analysis exposes terminal per-KC
states from the repository's existing fixed BKT transition rule.  States are
computed from public acquisition outcomes with the frozen true-K* projection,
then materialised before the private oracle is opened.  The oracle is used only
to evaluate each active probe KC against ``mastery_before[kc_id]``.

The BKT state is not the generator state: BKT is correctness-conditioned and
gives full outcome credit to every active KC, whereas the generator learns from
opportunities regardless of correctness.  The comparison is diagnostic within
the synthetic world and is not a claim about human mastery.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.experiments.full_v1_mastery_recovery import (  # noqa: E402
    CALIBRATION_BINS,
    DEFAULT_DATASET,
    DEFAULT_OUTPUT,
    DEFAULT_RQ2_DIR,
    GRAMMAR_REGIMES,
    ORACLE_SCHEMA,
    PAIR_FIELDS,
    _canonical_json,
    _declared_oracle,
    _deterministic_gzip,
    _event_key,
    _event_key_sha256,
    _load_and_validate_rq2,
    _read_manifest,
    _write_frozen_bytes,
    _write_frozen_json,
    file_sha256,
    load_observable_events,
)


STUDY_ID = "full_v1_secondary_fixed_bkt_terminal_kc_recovery_v1"
DEFAULT_PROTOCOL = ROOT / "modules/evaluation/kt/protocol.yaml"
REFERENCE_REPRESENTATION = "true_kstar"
STATE_SCHEMA = {"learner_id", "kc_id", "terminal_bkt_mastery"}


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


def _load_bkt_protocol(protocol_path: Path) -> tuple[dict[str, Any], dict[str, float]]:
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != "simple_online_kt_v1":
        raise ValueError("unexpected repository KT protocol")
    if "bkt" not in protocol.get("techniques", []):
        raise ValueError("repository KT protocol does not declare BKT")
    raw = protocol["bkt"]
    if set(raw) != {"initial_mastery", "learn", "guess", "slip"}:
        raise ValueError("repository BKT parameter schema changed")
    parameters = {key: float(value) for key, value in raw.items()}
    for key, value in parameters.items():
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"BKT parameter {key} must lie in [0, 1]")
    if parameters["guess"] + parameters["slip"] >= 1.0:
        raise ValueError("BKT guess and slip must sum to less than one")
    return protocol, parameters


def _bkt_transition(prior: float, correct: int, parameters: Mapping[str, float]) -> float:
    if correct not in (0, 1) or isinstance(correct, bool):
        raise ValueError("BKT outcome must be integer 0/1")
    guess = float(parameters["guess"])
    slip = float(parameters["slip"])
    learn = float(parameters["learn"])
    if correct:
        denominator = prior * (1.0 - slip) + (1.0 - prior) * guess
        posterior = prior * (1.0 - slip) / denominator
    else:
        denominator = prior * slip + (1.0 - prior) * (1.0 - guess)
        posterior = prior * slip / denominator
    updated = posterior + (1.0 - posterior) * learn
    if not math.isfinite(updated) or not 0.0 <= updated <= 1.0:
        raise ValueError("BKT transition produced an invalid state")
    return updated


def compute_terminal_bkt_states(
    events: Sequence[Mapping[str, Any]],
    projection: Mapping[str, Sequence[str]],
    parameters: Mapping[str, float],
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """Expose the terminal state of the repository's existing BKT rule."""

    required_parameters = {"initial_mastery", "learn", "guess", "slip"}
    if set(parameters) != required_parameters:
        raise ValueError("BKT parameters must exactly match the declared schema")
    initial = float(parameters["initial_mastery"])
    if not 0.0 <= initial <= 1.0:
        raise ValueError("BKT initial mastery must lie in [0, 1]")
    event_items = {str(event["item_id"]) for event in events}
    if event_items - set(projection):
        raise ValueError("true-Q projection lacks a public event item")
    kc_ids = sorted({str(kc_id) for active in projection.values() for kc_id in active})
    if not kc_ids or any(not active for active in projection.values()):
        raise ValueError("true-Q projection must activate at least one KC per item")
    learners = sorted({str(event["learner_id"]) for event in events})
    state = {
        learner_id: {kc_id: initial for kc_id in kc_ids}
        for learner_id in learners
    }
    probe_started: set[str] = set()
    acquisition_events = 0
    active_kc_updates = 0
    ignored_probe_outcomes = 0
    for event in sorted(
        events, key=lambda row: (str(row["learner_id"]), int(row["sequence_index"]))
    ):
        learner_id = str(event["learner_id"])
        phase = str(event["phase"])
        if phase == "probe":
            probe_started.add(learner_id)
            ignored_probe_outcomes += 1
            continue
        if phase != "acquisition":
            raise ValueError(f"unknown event phase: {phase}")
        if learner_id in probe_started:
            raise ValueError("acquisition follows terminal probe")
        if not bool(event.get("updates_history", True)):
            raise ValueError("public acquisition is unexpectedly non-updating")
        active = tuple(str(kc_id) for kc_id in projection[str(event["item_id"])])
        correct = event["correct"]
        for kc_id in active:
            state[learner_id][kc_id] = _bkt_transition(
                state[learner_id][kc_id], correct, parameters
            )
            active_kc_updates += 1
        acquisition_events += 1
    if probe_started != set(learners):
        raise ValueError("not every learner has a terminal probe")
    return state, {
        "learners": len(learners),
        "kcs": len(kc_ids),
        "terminal_learner_kc_states": len(learners) * len(kc_ids),
        "acquisition_events_used": acquisition_events,
        "active_kc_full_credit_updates": active_kc_updates,
        "probe_outcomes_ignored": ignored_probe_outcomes,
        "all_terminal_states_finite_and_bounded": all(
            math.isfinite(value) and 0.0 <= value <= 1.0
            for learner_state in state.values()
            for value in learner_state.values()
        ),
    }


def render_terminal_states(states: Mapping[str, Mapping[str, float]]) -> bytes:
    payload = "".join(
        _canonical_json(
            {
                "learner_id": learner_id,
                "kc_id": kc_id,
                "terminal_bkt_mastery": float(states[learner_id][kc_id]),
            }
        )
        + "\n"
        for learner_id in sorted(states)
        for kc_id in sorted(states[learner_id])
    ).encode("utf-8")
    return _deterministic_gzip(payload)


def _public_input_records(
    dataset_dir: Path, rq2_dir: Path, protocol_path: Path
) -> dict[str, Any]:
    rq2_plan = json.loads((rq2_dir / "study_plan.json").read_text(encoding="utf-8"))
    paths = {
        "dataset_manifest": dataset_dir / "manifest.json",
        "observable_interactions": dataset_dir / "interactions.jsonl.gz",
        "rq2_study_plan": rq2_dir / "study_plan.json",
        "rq2_projection_bundle": rq2_dir / "projections.jsonl",
        "declared_kt_protocol": protocol_path,
        "existing_bkt_implementation": ROOT / "src/grammar_kt/kt.py",
        "rq2_projection_implementation": ROOT
        / str(rq2_plan["implementation"]["script"]),
    }
    return {
        name: {
            "path": str(path.relative_to(ROOT)),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for name, path in paths.items()
    }


def create_plan(
    dataset_dir: Path,
    rq2_dir: Path,
    protocol_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    manifest = _read_manifest(dataset_dir)
    _rq2_plan, projections = _load_and_validate_rq2(rq2_dir)
    _protocol, parameters = _load_bkt_protocol(protocol_path)
    true_projection = projections[REFERENCE_REPRESENTATION]
    script_path = Path(__file__).resolve()
    generator = manifest["simulation"]["pilot"]["condition"]
    plan = {
        "study_id": STUDY_ID,
        "status": "SECONDARY_FIXED_ANALYSIS_PLAN_LOCKED_BEFORE_BKT_STATE_EVALUATION",
        "classification": (
            "Secondary model-exposed mastery analysis requested after the primary "
            "inverse-link study; not a replacement primary estimand."
        ),
        "model": {
            "name": "repository fixed BKT with exposed terminal per-KC state",
            "parameter_source": str(protocol_path.relative_to(ROOT)),
            "parameters": parameters,
            "parameters_fit_or_tuned": False,
            "projection": REFERENCE_REPRESENTATION,
            "projection_label": "frozen true K*/Q*",
            "public_inputs": "acquisition item IDs, order, and binary outcomes only",
            "probe_outcomes_used": False,
            "state_timing": "after all acquisition updates and before terminal probes",
            "multi_kc_update": (
                "the same item outcome is treated as full evidence for every active KC, "
                "matching src/grammar_kt/kt.py::_bkt"
            ),
        },
        "generator_mismatch": {
            "deliberately_misspecified": True,
            "bkt_initial_mastery": "fixed 0.35",
            "generator_initial_mastery": "learner-KC Beta(2,2) draws",
            "bkt_learning": (
                "correctness-conditioned Bayesian posterior followed by learn=0.12"
            ),
            "generator_learning": (
                f"outcome-independent all-active opportunity update at rate "
                f"{float(generator['learning_rate'])}"
            ),
            "bkt_multi_kc_credit": "full item outcome applied to every active KC",
            "generator_response_aggregation": str(generator["aggregation"]),
            "bkt_response_aggregation": "mean active KC state in existing implementation",
            "bkt_guess_slip": [parameters["guess"], parameters["slip"]],
            "generator_guess_slip": [
                float(generator["guess"]),
                float(generator["slip"]),
            ],
            "interpretation": (
                "Agreement is not expected by construction; this evaluates whether a "
                "standard fixed BKT state tracks the different generator state."
            ),
        },
        "evaluation": {
            "oracle_target": "mastery_before[kc_id] for every active KC on each terminal probe",
            "metrics": [
                "RMSE",
                "MAE",
                "Pearson correlation",
                "10-bin fixed-width KC-state calibration",
            ],
            "regimes": ["all_probe", *GRAMMAR_REGIMES],
            "primary_weighting_within_secondary": "event-active-KC pair weighted",
            "additional_weighting": "unique terminal learner-KC pairs overall",
            "join_key": ["learner_id", "sequence_index"],
            "paired_fields_checked": list(PAIR_FIELDS),
            "oracle_active_kcs_checked_against_true_q": True,
        },
        "leakage_controls": {
            "terminal_bkt_states_frozen_before_oracle_open": True,
            "oracle_fit_tuning_or_state_update": False,
            "oracle_use": "secondary evaluation target only",
        },
        "true_projection_structure": {
            "items": len(true_projection),
            "kcs": len(
                {kc_id for active in true_projection.values() for kc_id in active}
            ),
            "edges": sum(len(active) for active in true_projection.values()),
        },
        "public_inputs": _public_input_records(
            dataset_dir, rq2_dir, protocol_path
        ),
        "private_oracle_declared_but_not_opened_by_plan": _declared_oracle(manifest),
        "implementation": {
            "script": str(script_path.relative_to(ROOT)),
            "script_sha256": file_sha256(script_path),
            "repository_head_at_secondary_plan": _repository_head(),
            "python": sys.version.split()[0],
            "numpy": np.__version__,
        },
        "exact_commands": {
            "plan": ".venv/bin/python scripts/experiments/full_v1_bkt_state_recovery.py --stage plan",
            "run": ".venv/bin/python scripts/experiments/full_v1_bkt_state_recovery.py --stage run",
            "test": ".venv/bin/python -m pytest -q tests/test_full_v1_bkt_state_recovery.py",
        },
    }
    _write_frozen_json(
        output_dir / "secondary_bkt_plan.json", plan, "secondary BKT plan"
    )
    return plan


def _validate_plan(
    dataset_dir: Path,
    rq2_dir: Path,
    protocol_path: Path,
    output_dir: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, tuple[str, ...]],
    dict[str, float],
]:
    plan_path = output_dir / "secondary_bkt_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError("run requires secondary_bkt_plan.json")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("study_id") != STUDY_ID:
        raise ValueError("unexpected secondary BKT study ID")
    if plan.get("status") != (
        "SECONDARY_FIXED_ANALYSIS_PLAN_LOCKED_BEFORE_BKT_STATE_EVALUATION"
    ):
        raise ValueError("secondary BKT plan is not locked")
    if plan["implementation"]["script_sha256"] != file_sha256(Path(__file__).resolve()):
        raise ValueError("secondary BKT implementation changed after planning")
    if plan["public_inputs"] != _public_input_records(
        dataset_dir, rq2_dir, protocol_path
    ):
        raise ValueError("secondary BKT public inputs changed after planning")
    manifest = _read_manifest(dataset_dir)
    if plan["private_oracle_declared_but_not_opened_by_plan"] != _declared_oracle(
        manifest
    ):
        raise ValueError("manifest-declared oracle metadata changed")
    _rq2_plan, projections = _load_and_validate_rq2(rq2_dir)
    _protocol, parameters = _load_bkt_protocol(protocol_path)
    if plan["model"]["parameters"] != parameters:
        raise ValueError("declared fixed BKT parameters changed")
    return plan, manifest, projections[REFERENCE_REPRESENTATION], parameters


def _state_calibration(
    oracle: np.ndarray, estimate: np.ndarray, *, bins: int
) -> dict[str, Any]:
    edges = np.linspace(0.0, 1.0, bins + 1)
    table: list[dict[str, Any]] = []
    expected_gap = 0.0
    maximum_gap = 0.0
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
            expected_gap += count / len(estimate) * abs(gap)
            maximum_gap = max(maximum_gap, abs(gap))
        else:
            estimate_mean = None
            oracle_mean = None
            gap = None
        table.append(
            {
                "bin_index": index + 1,
                "lower_inclusive": float(edges[index]),
                "upper_inclusive_only_for_last_bin": float(edges[index + 1]),
                "n": count,
                "mean_estimated_terminal_bkt_kc_state": estimate_mean,
                "mean_oracle_kc_mastery_before": oracle_mean,
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
            "Calibration compares exposed terminal BKT KC state with oracle "
            "mastery_before[kc_id] in fixed-width estimate bins."
        ),
        "bins": bins,
        "mean_estimate_minus_oracle": float(np.mean(estimate - oracle)),
        "fixed_bin_expected_absolute_gap": float(expected_gap),
        "maximum_nonempty_bin_absolute_gap": float(maximum_gap),
        "linear_truth_on_estimate_intercept": intercept,
        "linear_truth_on_estimate_slope": slope,
        "bin_table": table,
    }


def kc_state_recovery_metrics(
    oracle_values: Sequence[float] | np.ndarray,
    estimated_states: Sequence[float] | np.ndarray,
    *,
    bins: int = CALIBRATION_BINS,
) -> dict[str, Any]:
    oracle = np.asarray(oracle_values, dtype=float)
    estimate = np.asarray(estimated_states, dtype=float)
    if oracle.ndim != 1 or estimate.ndim != 1 or len(oracle) != len(estimate):
        raise ValueError("oracle KC values and BKT states must pair exactly")
    if not len(oracle):
        return {
            "n": 0,
            "rmse": None,
            "mae": None,
            "pearson_correlation": None,
            "calibration": None,
        }
    if (
        not np.all(np.isfinite(oracle))
        or not np.all(np.isfinite(estimate))
        or np.any(oracle < 0.0)
        or np.any(oracle > 1.0)
        or np.any(estimate < 0.0)
        or np.any(estimate > 1.0)
    ):
        raise ValueError("oracle KC values and BKT states must be finite in [0, 1]")
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
        "calibration": _state_calibration(oracle, estimate, bins=bins),
    }


def _evaluate_oracle_after_state_freeze(
    oracle_path: Path,
    public_events: Sequence[Mapping[str, Any]],
    projection: Mapping[str, Sequence[str]],
    states: Mapping[str, Mapping[str, float]],
    *,
    state_artifact_path: Path,
    state_artifact_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not state_artifact_path.is_file():
        raise FileNotFoundError("terminal BKT states must be frozen before oracle open")
    if file_sha256(state_artifact_path) != state_artifact_sha256:
        raise ValueError("terminal BKT state artifact changed before oracle evaluation")
    public_by_key: dict[tuple[str, int], Mapping[str, Any]] = {}
    for event in public_events:
        key = _event_key(event)
        if key in public_by_key:
            raise ValueError(f"duplicate public event key: {key}")
        public_by_key[key] = event
    oracle_keys: set[tuple[str, int]] = set()
    estimates_by_regime: dict[str, list[float]] = defaultdict(list)
    oracle_by_regime: dict[str, list[float]] = defaultdict(list)
    unique_oracle: dict[tuple[str, str], float] = {}
    active_pair_count = 0
    with gzip.open(oracle_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if set(row) != ORACLE_SCHEMA:
                raise ValueError("private-oracle schema changed")
            key = _event_key(row)
            if key in oracle_keys:
                raise ValueError(f"duplicate oracle event key: {key}")
            oracle_keys.add(key)
            public = public_by_key.get(key)
            if public is None:
                raise ValueError(f"oracle key absent from public events: {key}")
            for field in PAIR_FIELDS:
                if row[field] != public[field]:
                    raise ValueError(f"oracle/public mismatch at {key} for {field}")
            active = tuple(str(kc_id) for kc_id in row["active_generator_kc_ids"])
            expected_active = tuple(
                str(kc_id) for kc_id in projection[str(row["item_id"])]
            )
            if active != expected_active:
                raise ValueError(f"oracle active KCs differ from true Q* at {key}")
            before = row["mastery_before"]
            if not isinstance(before, dict) or list(before) != list(active):
                raise ValueError(f"oracle mastery-before scope differs from active KCs at {key}")
            if row["phase"] != "probe":
                continue
            learner_id = key[0]
            regime = str(row["grammar_regime"])
            if regime not in GRAMMAR_REGIMES:
                raise ValueError(f"unknown probe grammar regime: {regime}")
            for kc_id in active:
                value = before[kc_id]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError("oracle KC mastery must be numeric")
                oracle_value = float(value)
                if not math.isfinite(oracle_value) or not 0.0 <= oracle_value <= 1.0:
                    raise ValueError("oracle KC mastery must lie in [0, 1]")
                estimated = float(states[learner_id][kc_id])
                estimates_by_regime[regime].append(estimated)
                oracle_by_regime[regime].append(oracle_value)
                pair_key = (learner_id, kc_id)
                previous = unique_oracle.get(pair_key)
                if previous is not None and previous != oracle_value:
                    raise ValueError("non-updating probes disagree on terminal oracle KC state")
                unique_oracle[pair_key] = oracle_value
                active_pair_count += 1
    if oracle_keys != set(public_by_key):
        raise ValueError("oracle/public event key sets differ")
    expected_unique = {
        (learner_id, kc_id)
        for learner_id, learner_states in states.items()
        for kc_id in learner_states
    }
    if set(unique_oracle) != expected_unique:
        raise ValueError("terminal probes do not identify every learner-KC oracle state")
    all_estimates = np.concatenate(
        [np.asarray(estimates_by_regime[regime]) for regime in GRAMMAR_REGIMES]
    )
    all_oracle = np.concatenate(
        [np.asarray(oracle_by_regime[regime]) for regime in GRAMMAR_REGIMES]
    )
    metrics_by_regime = {
        "all_probe": kc_state_recovery_metrics(all_oracle, all_estimates),
        **{
            regime: kc_state_recovery_metrics(
                oracle_by_regime[regime], estimates_by_regime[regime]
            )
            for regime in GRAMMAR_REGIMES
        },
    }
    ordered_unique = sorted(unique_oracle)
    unique_metrics = kc_state_recovery_metrics(
        [unique_oracle[key] for key in ordered_unique],
        [states[key[0]][key[1]] for key in ordered_unique],
    )
    return {
        "event_active_kc_weighted_metrics_by_regime": metrics_by_regime,
        "unique_terminal_learner_kc_metrics": unique_metrics,
    }, {
        "join_key": ["learner_id", "sequence_index"],
        "paired_fields_checked": list(PAIR_FIELDS),
        "public_events": len(public_by_key),
        "oracle_events": len(oracle_keys),
        "terminal_probe_active_kc_pairs": active_pair_count,
        "unique_terminal_learner_kc_pairs": len(unique_oracle),
        "all_public_oracle_keys_match": True,
        "all_oracle_active_kcs_match_true_q": True,
        "all_repeated_probe_kc_truth_is_constant": True,
        "public_event_key_sha256": _event_key_sha256(public_by_key),
    }


def run_study(
    dataset_dir: Path,
    rq2_dir: Path,
    protocol_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    plan, manifest, projection, parameters = _validate_plan(
        dataset_dir, rq2_dir, protocol_path, output_dir
    )
    events = load_observable_events(dataset_dir / "interactions.jsonl.gz")
    if len(events) != int(manifest["scale"]["interactions"]):
        raise ValueError("public event count differs from frozen full-v1 manifest")
    states, state_audit = compute_terminal_bkt_states(events, projection, parameters)
    if len(states) != int(manifest["scale"]["learners"]):
        raise ValueError("BKT state artifact does not cover every learner")
    state_path = output_dir / "secondary_bkt_terminal_kc_states.jsonl.gz"
    _write_frozen_bytes(
        state_path,
        render_terminal_states(states),
        "secondary terminal BKT KC states",
    )
    state_sha256 = file_sha256(state_path)
    print(f"froze public-only terminal BKT states before oracle access: {state_path}", flush=True)

    oracle_declared = plan["private_oracle_declared_but_not_opened_by_plan"]
    oracle_path = dataset_dir / str(oracle_declared["path"])
    oracle_actual_sha256 = file_sha256(oracle_path)
    if oracle_actual_sha256 != oracle_declared["sha256"]:
        raise ValueError("private oracle hash differs from frozen manifest")
    metrics, join_audit = _evaluate_oracle_after_state_freeze(
        oracle_path,
        events,
        projection,
        states,
        state_artifact_path=state_path,
        state_artifact_sha256=state_sha256,
    )
    result = {
        "study_id": STUDY_ID,
        "status": "FINAL_SECONDARY_FIXED_BKT_STATE_RECOVERY",
        "classification": plan["classification"],
        "secondary_plan_sha256": file_sha256(output_dir / "secondary_bkt_plan.json"),
        "terminal_state_artifact": {
            "path": state_path.name,
            "sha256": state_sha256,
            "bytes": state_path.stat().st_size,
            "rows": state_audit["terminal_learner_kc_states"],
            "contains_private_oracle_fields": False,
            "frozen_before_private_oracle_open": True,
        },
        "private_oracle_evaluation": {
            "declared_sha256": oracle_declared["sha256"],
            "actual_sha256_after_states_frozen": oracle_actual_sha256,
            "fit_tuning_or_state_update": False,
            "target": "mastery_before[kc_id]",
        },
        "fixed_bkt_parameters": parameters,
        "state_construction_audit": state_audit,
        "join_audit": join_audit,
        **metrics,
        "deliberate_model_generator_mismatch": plan["generator_mismatch"],
        "interpretation_boundary": (
            "These are exposed states of a deliberately misspecified fixed BKT, "
            "not inverse-link item states, generator parameters, logistic coefficients, "
            "or human mastery estimates."
        ),
    }
    result_path = output_dir / "secondary_bkt_state_recovery.json"
    _write_frozen_json(result_path, result, "secondary BKT state-recovery result")
    artifact_manifest = {
        "study_id": STUDY_ID,
        "classification": "secondary fixed-BKT state recovery",
        "artifacts": {
            path.name: {
                "sha256": file_sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (
                output_dir / "secondary_bkt_plan.json",
                state_path,
                result_path,
            )
        },
    }
    _write_frozen_json(
        output_dir / "secondary_bkt_artifact_manifest.json",
        artifact_manifest,
        "secondary BKT artifact manifest",
    )
    print(f"wrote {result_path}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("plan", "run"), required=True)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--rq2-dir", type=Path, default=DEFAULT_RQ2_DIR)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    dataset_dir = args.dataset_dir.resolve()
    rq2_dir = args.rq2_dir.resolve()
    protocol_path = args.protocol.resolve()
    output_dir = args.output_dir.resolve()
    if args.stage == "plan":
        create_plan(dataset_dir, rq2_dir, protocol_path, output_dir)
        print(f"locked secondary fixed-BKT analysis at {output_dir}", flush=True)
        return 0
    run_study(dataset_dir, rq2_dir, protocol_path, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
