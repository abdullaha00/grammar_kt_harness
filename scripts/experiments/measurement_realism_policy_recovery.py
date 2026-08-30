#!/usr/bin/env python3
"""Freeze, aggregate, and verify the derived assignment-policy analysis.

The response streams were preregistered in the controlled-instrument study,
but model fitting for the three platform-oriented policies was not part of the
confirmatory 18-run analysis matrix.  This script therefore preserves an
append-only, explicitly post-response analysis record.  It never generates or
changes learner responses and never upgrades the content-free instrument into
a learner-facing dataset.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import tempfile
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
WORLD_ROOT = ROOT / "experiments/measurement_realism/worlds/controlled_instrument_v1"
DERIVED_ROOT = WORLD_ROOT / "policy_recovery_v1"
RUNNER = ROOT / "scripts/experiments/measurement_realism_worlds.py"
CONFIG = ROOT / "experiments/measurement_realism/design/controlled_instrument_v1/scenario_config.yaml"
POLICIES = ("curriculum", "mixed_practice", "adaptive_weakness")
REFERENCE_POLICY = "q_balanced_lab"
WORLD_ID = "combined_heterogeneous"
PRIMARY_CONDITION = "D"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def write_frozen_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_name(policy: str, seed: int) -> str:
    return f"{WORLD_ID}__{policy}__seed_{seed}"


def response_manifest_path(policy: str, seed: int) -> Path:
    return WORLD_ROOT / "runs" / run_name(policy, seed) / "run_manifest.json"


def analysis_dir(policy: str, seed: int) -> Path:
    return WORLD_ROOT / "runs" / run_name(policy, seed) / "analysis"


def study_plan() -> dict[str, Any]:
    path = WORLD_ROOT / "study_plan.json"
    plan = load_json(path)
    if plan.get("controlled_scenario") is not True or plan.get("release_eligible") is not False:
        raise ValueError("policy derivation requires the non-release controlled study")
    return plan


def build_plan() -> dict[str, Any]:
    base = study_plan()
    seeds = [int(seed) for seed in base["seeds"]]
    records = []
    for policy in POLICIES:
        for seed in seeds:
            manifest_path = response_manifest_path(policy, seed)
            if not manifest_path.is_file():
                raise FileNotFoundError(manifest_path)
            if analysis_dir(policy, seed).exists():
                raise ValueError(
                    "derived plan must be frozen before the platform-policy model fits: "
                    f"{analysis_dir(policy, seed)}"
                )
            manifest = load_json(manifest_path)
            if (
                manifest.get("world_id") != WORLD_ID
                or manifest.get("policy_id") != policy
                or manifest.get("seed") != seed
                or manifest.get("controlled_scenario") is not True
                or manifest.get("release_eligible") is not False
            ):
                raise ValueError(f"response identity mismatch: {manifest_path}")
            reference_analysis_manifest = analysis_dir(REFERENCE_POLICY, seed) / "analysis_manifest.json"
            if not reference_analysis_manifest.is_file():
                raise FileNotFoundError(reference_analysis_manifest)
            records.append(
                {
                    "policy_id": policy,
                    "seed": seed,
                    "response_manifest": str(manifest_path.relative_to(ROOT)),
                    "response_manifest_sha256": sha256_file(manifest_path),
                    "reference_analysis_manifest": str(reference_analysis_manifest.relative_to(ROOT)),
                    "reference_analysis_manifest_sha256": sha256_file(reference_analysis_manifest),
                }
            )
    return {
        "analysis_id": "measurement_realism_policy_recovery_v1",
        "status": "FROZEN_POST_RESPONSE_BEFORE_POLICY_MODEL_FITS",
        "date_frozen": "2026-08-30",
        "timing_disclosure": {
            "response_streams_already_generated": True,
            "descriptive_schedule_diagnostics_already_inspected": True,
            "confirmatory_cross_world_aggregate_already_inspected": True,
            "platform_policy_model_fits_already_run": False,
            "classification": "derived_exploratory_policy_robustness_not_preregistered_confirmatory_evidence",
        },
        "claim_boundary": {
            "controlled_scenario": True,
            "release_eligible": False,
            "learner_facing_items": False,
            "platform_policy_efficacy_claim": False,
            "interpretation": (
                "same frozen observable model applied to policy-selected histories; "
                "differences combine exposure, learned state, outcomes, and model fit"
            ),
        },
        "inputs": {
            "study_plan": str((WORLD_ROOT / "study_plan.json").relative_to(ROOT)),
            "study_plan_sha256": sha256_file(WORLD_ROOT / "study_plan.json"),
            "confirmatory_aggregate": str((WORLD_ROOT / "aggregate/results.json").relative_to(ROOT)),
            "confirmatory_aggregate_sha256": sha256_file(WORLD_ROOT / "aggregate/results.json"),
            "analysis_runner": str(RUNNER.relative_to(ROOT)),
            "analysis_runner_sha256": sha256_file(RUNNER),
            "config": str(CONFIG.relative_to(ROOT)),
            "config_sha256": sha256_file(CONFIG),
        },
        "world_id": WORLD_ID,
        "reference_policy": REFERENCE_POLICY,
        "policies": list(POLICIES),
        "seeds": seeds,
        "primary_model_condition": PRIMARY_CONDITION,
        "estimands": {
            "primary_prediction": "condition_D_seen_terminal_probe_log_loss",
            "secondary_prediction": [
                "condition_A_to_D_seen_log_loss_brier_ece_auc",
                "condition_D_all_terminal_probe_log_loss",
            ],
            "oracle_diagnostics": [
                "condition_D_seen_item_prerequisite_state_rmse",
                "binary_evidence_count_terminal_Kstar_rmse",
            ],
            "exposure": "frozen_schedule_diagnostics",
            "uncertainty": (
                "learner-paired bootstrap conditional on each frozen fit and seed; "
                "three-seed mean/min/max are descriptive"
            ),
        },
        "important_invariance": (
            "q_balanced, curriculum, and mixed use the same occurrence multiset; "
            "with order-independent unconditional learning they have identical terminal "
            "oracle mastery by construction, so order comparisons concern history and fit, not efficacy"
        ),
        "runs": records,
        "commands": [
            (
                ".venv/bin/python scripts/experiments/measurement_realism_worlds.py "
                "--stage analyze --controlled-scenario "
                "--config experiments/measurement_realism/design/controlled_instrument_v1/scenario_config.yaml "
                "--output-dir experiments/measurement_realism/worlds/controlled_instrument_v1 "
                f"--world {WORLD_ID} --seed {seed} --policy {policy}"
            )
            for policy in POLICIES
            for seed in seeds
        ],
    }


def plan_run_input_paths(plan: Mapping[str, Any]) -> list[Path]:
    return [
        ROOT / record[key]
        for record in plan["runs"]
        for key in ("response_manifest", "reference_analysis_manifest")
    ]


def run_inputs_present(plan: Mapping[str, Any]) -> bool:
    states = [path.is_file() for path in plan_run_input_paths(plan)]
    if any(states) and not all(states):
        raise ValueError("policy verification found a partial raw-run input tree")
    return all(states)


def validate_plan(
    path: Path, *, allow_missing_run_inputs: bool = False
) -> dict[str, Any]:
    plan = load_json(path)
    if plan.get("analysis_id") != "measurement_realism_policy_recovery_v1":
        raise ValueError("unexpected derived policy analysis id")
    inputs = plan["inputs"]
    for key, expected in (
        ("study_plan", inputs["study_plan_sha256"]),
        ("confirmatory_aggregate", inputs["confirmatory_aggregate_sha256"]),
        ("analysis_runner", inputs["analysis_runner_sha256"]),
        ("config", inputs["config_sha256"]),
    ):
        actual = sha256_file(ROOT / inputs[key])
        if actual != expected:
            raise ValueError(f"derived policy input hash drift: {key}")
    raw_inputs_present = run_inputs_present(plan)
    if not raw_inputs_present and not allow_missing_run_inputs:
        raise FileNotFoundError(
            "raw policy-run inputs are absent; use compact verification or "
            "regenerate the controlled response runs"
        )
    for record in plan["runs"] if raw_inputs_present else []:
        if sha256_file(ROOT / record["response_manifest"]) != record["response_manifest_sha256"]:
            raise ValueError("policy response manifest hash drift")
        if sha256_file(ROOT / record["reference_analysis_manifest"]) != record["reference_analysis_manifest_sha256"]:
            raise ValueError("reference analysis manifest hash drift")
    return plan


def read_jsonl_gz(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def mean_min_max(values: Iterable[float]) -> dict[str, Any]:
    sequence = [float(value) for value in values]
    return {
        "n_seeds": len(sequence),
        "mean": fmean(sequence),
        "minimum": min(sequence),
        "maximum": max(sequence),
        "values": sequence,
    }


def learner_losses(rows: Iterable[Mapping[str, Any]], condition: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    probability_key = f"probability_{condition}"
    for row in rows:
        if row["grammar_regime"] != "seen":
            continue
        probability = min(max(float(row[probability_key]), 1e-12), 1.0 - 1e-12)
        target = int(row["correct"])
        grouped[str(row["learner_id"])].append(
            -(target * math.log(probability) + (1 - target) * math.log(1 - probability))
        )
    return {learner: fmean(losses) for learner, losses in grouped.items()}


def paired_interval(
    reference: Mapping[str, float],
    candidate: Mapping[str, float],
    *,
    seed: int,
    repeats: int = 2000,
) -> dict[str, Any]:
    if set(reference) != set(candidate):
        raise ValueError("policy comparison learner sets differ")
    learners = sorted(reference)
    delta = np.asarray([candidate[learner] - reference[learner] for learner in learners])
    rng = np.random.default_rng(seed)
    draws = np.empty(repeats, dtype=float)
    for index in range(repeats):
        draws[index] = float(np.mean(delta[rng.integers(0, len(delta), len(delta))]))
    return {
        "delta": "policy_minus_q_balanced_lab",
        "learners": len(learners),
        "point_estimate": float(np.mean(delta)),
        "percentile_95": [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))],
        "repeats": repeats,
        "scope": "conditional_on_each_frozen_fit_seed_bank_and_simulator_world",
    }


def build_results(plan: Mapping[str, Any]) -> dict[str, Any]:
    policies = [REFERENCE_POLICY, *POLICIES]
    seeds = [int(seed) for seed in plan["seeds"]]
    per_policy: dict[str, dict[str, Any]] = {}
    predictions: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for policy in policies:
        per_seed: dict[str, Any] = {}
        for seed in seeds:
            directory = analysis_dir(policy, seed)
            manifest_path = directory / "analysis_manifest.json"
            results_path = directory / "model_results.json"
            predictions_path = directory / "test_predictions.jsonl.gz"
            for path in (manifest_path, results_path, predictions_path):
                if not path.is_file():
                    raise FileNotFoundError(path)
            manifest = load_json(manifest_path)
            if (
                manifest.get("world_id") != WORLD_ID
                or manifest.get("policy_id") != policy
                or manifest.get("seed") != seed
                or manifest.get("controlled_scenario") is not True
            ):
                raise ValueError(f"policy analysis identity mismatch: {manifest_path}")
            model = load_json(results_path)
            predictions[(policy, seed)] = read_jsonl_gz(predictions_path)
            conditions = model["conditions"]
            per_seed[str(seed)] = {
                "condition_metrics_seen": {
                    condition: {
                        key: conditions[condition]["metrics"][key]
                        for key in (
                            "log_loss",
                            "brier_score",
                            "ece_10_fixed_width",
                            "roc_auc",
                        )
                    }
                    for condition in ("A", "B", "C", "D")
                },
                "condition_D_item_prerequisite_state_recovery": conditions["D"]["state_recovery"],
                "binary_terminal_Kstar_evidence_diagnostic": model[
                    "terminal_kc_state_recovery_secondary"
                ],
                "analysis_manifest_sha256": sha256_file(manifest_path),
                "test_predictions_sha256": sha256_file(predictions_path),
            }
        per_policy[policy] = {
            "per_seed": per_seed,
            "condition_D_seen_log_loss": mean_min_max(
                per_seed[str(seed)]["condition_metrics_seen"]["D"]["log_loss"]
                for seed in seeds
            ),
            "condition_D_seen_item_prerequisite_state_rmse": mean_min_max(
                per_seed[str(seed)]["condition_D_item_prerequisite_state_recovery"][
                    "item_prerequisite_state_rmse"
                ]
                for seed in seeds
            ),
            "binary_terminal_Kstar_evidence_rmse": mean_min_max(
                per_seed[str(seed)]["binary_terminal_Kstar_evidence_diagnostic"]["rmse"]
                for seed in seeds
            ),
        }
    comparisons: dict[str, Any] = {}
    for policy_index, policy in enumerate(POLICIES, start=1):
        per_seed = {}
        for seed in seeds:
            reference_rows = predictions[(REFERENCE_POLICY, seed)]
            candidate_rows = predictions[(policy, seed)]
            reference_keys = [
                (row["learner_id"], row["item_id"], row["grammar_regime"])
                for row in reference_rows
            ]
            candidate_keys = [
                (row["learner_id"], row["item_id"], row["grammar_regime"])
                for row in candidate_rows
            ]
            if reference_keys != candidate_keys:
                raise ValueError(f"terminal evaluation rows differ for {policy}/{seed}")
            per_seed[str(seed)] = paired_interval(
                learner_losses(reference_rows, PRIMARY_CONDITION),
                learner_losses(candidate_rows, PRIMARY_CONDITION),
                seed=20260830 + policy_index * 100 + seed % 100,
            )
        comparisons[f"{policy}_minus_{REFERENCE_POLICY}"] = {
            "per_seed": per_seed,
            "point_estimate_summary": mean_min_max(
                per_seed[str(seed)]["point_estimate"] for seed in seeds
            ),
        }
    return {
        "analysis_id": plan["analysis_id"],
        "classification": plan["timing_disclosure"]["classification"],
        "controlled_scenario": True,
        "release_eligible": False,
        "world_id": WORLD_ID,
        "primary_condition": PRIMARY_CONDITION,
        "policy_results": per_policy,
        "learner_paired_seen_log_loss_comparisons": comparisons,
        "interpretation_limits": [
            plan["important_invariance"],
            plan["claim_boundary"]["interpretation"],
            "item-prerequisite state RMSE is not learner-by-KC mastery RMSE",
            "terminal Kstar recovery is a transparent Beta evidence-count diagnostic, not a fitted KT state",
            "bootstrap intervals condition on each frozen fit and do not include refitting, bank, seed, or simulator uncertainty",
        ],
    }


def command_plan() -> None:
    path = DERIVED_ROOT / "plan.json"
    plan = build_plan()
    write_frozen_json(path, plan)
    print(json.dumps({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)}, sort_keys=True))


def command_validate() -> None:
    path = DERIVED_ROOT / "plan.json"
    plan = validate_plan(path)
    print(json.dumps({"analysis_id": plan["analysis_id"], "sha256": sha256_file(path), "status": "PASS"}, sort_keys=True))


def command_aggregate() -> None:
    plan_path = DERIVED_ROOT / "plan.json"
    plan = validate_plan(plan_path)
    results = build_results(plan)
    results_dir = DERIVED_ROOT / "results"
    if results_dir.exists():
        raise FileExistsError(f"refusing to overwrite derived results: {results_dir}")
    staging = Path(tempfile.mkdtemp(prefix=".results.incomplete.", dir=DERIVED_ROOT))
    results_path = staging / "results.json"
    results_path.write_bytes(canonical_bytes(results))
    manifest = {
        "analysis_id": plan["analysis_id"],
        "controlled_scenario": True,
        "release_eligible": False,
        "plan_sha256": sha256_file(plan_path),
        "artifacts": {"results.json": sha256_file(results_path)},
    }
    (staging / "manifest.json").write_bytes(canonical_bytes(manifest))
    staging.rename(results_dir)
    print(json.dumps(manifest, sort_keys=True))


def command_verify() -> None:
    plan_path = DERIVED_ROOT / "plan.json"
    stored_plan = load_json(plan_path)
    raw_inputs_present = run_inputs_present(stored_plan)
    plan = validate_plan(plan_path, allow_missing_run_inputs=True)
    results_dir = DERIVED_ROOT / "results"
    manifest = load_json(results_dir / "manifest.json")
    if manifest.get("plan_sha256") != sha256_file(plan_path):
        raise ValueError("derived result plan hash mismatch")
    actual = sha256_file(results_dir / "results.json")
    if manifest.get("artifacts") != {"results.json": actual}:
        raise ValueError("derived result artifact hash mismatch")
    results = load_json(results_dir / "results.json")
    if results.get("analysis_id") != plan["analysis_id"] or results.get("release_eligible") is not False:
        raise ValueError("derived result identity/claim boundary mismatch")
    print(
        json.dumps(
            {
                "analysis_id": plan["analysis_id"],
                "status": "PASS",
                "results_sha256": actual,
                "verification_scope": (
                    "raw_run_inputs_and_compact_results"
                    if raw_inputs_present
                    else "compact_results_bundle_only"
                ),
                "raw_run_inputs_present": raw_inputs_present,
                "raw_runs_reconstructable_from_frozen_plan": True,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("plan", "validate-plan", "aggregate", "verify"))
    args = parser.parse_args()
    {
        "plan": command_plan,
        "validate-plan": command_validate,
        "aggregate": command_aggregate,
        "verify": command_verify,
    }[args.stage]()


if __name__ == "__main__":
    main()
